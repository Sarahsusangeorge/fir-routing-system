"""
Authentication and role-based access control.

Three roles:
  citizen -- signs in with a one-time code sent to their email or mobile
             number; files complaints and tracks their own.
  officer -- signs in with a username (or email) and password; works the
             cases allocated to them and can see every case in the district.
  admin   -- signs in with a password; sees every case, reassigns cases and
             manages staff accounts.

Staff accounts are created by an administrator (see admin.py and
create_admin.py). There is no self-registration for staff.

Sessions are signed JWTs held in httpOnly cookies, so page scripts can never
read them. Every state-changing request must also carry the CSRF token in an
X-CSRF-TOKEN header (double-submit protection, handled by
Flask-JWT-Extended). The role is read from the database on every request
rather than trusted from the token, so deactivating an account takes effect
immediately.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    current_user,
    get_csrf_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
    verify_jwt_in_request,
)
from werkzeug.exceptions import BadRequest
from werkzeug.security import check_password_hash, generate_password_hash

import db

bp = Blueprint("auth", __name__, url_prefix="/api/auth")
jwt = JWTManager()

STAFF_ROLES = ("officer", "admin")

ACCESS_TOKEN_MINUTES = 60
REFRESH_WINDOW_MINUTES = 30      # re-issue the token when less than this remains

CODE_TTL_MINUTES = 10
CODE_MAX_ATTEMPTS = 5
CODE_RESEND_COOLDOWN_SECONDS = 60
CODE_MAX_PER_IDENTIFIER = 5      # per window
CODE_MAX_PER_IP = 20             # per window

LOGIN_MAX_FAILS_PER_EMAIL = 5    # per window
LOGIN_MAX_FAILS_PER_IP = 20      # per window
RATE_WINDOW_SECONDS = 15 * 60

MIN_PASSWORD_LENGTH = 10
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
INDIAN_MOBILE_RE = re.compile(r"^[6-9]\d{9}$")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRET_FILE = os.path.join(BASE_DIR, ".jwt_secret")

# A sign-in stays valid at most this long, however often the sliding renewal
# below re-issues the token.
MAX_SESSION_HOURS = 12

# Wrong one-time codes allowed per address across all codes in the window.
# Requesting a fresh code does not reset this, so an attacker cannot turn the
# per-code limit into unlimited guesses.
OTP_FAIL_LIMIT = 15
OTP_FAIL_WINDOW_SECONDS = 6 * 3600

_DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(16))

PURPOSE_SIGN_IN = "sign-in"
PURPOSE_NUMBER_CHANGE = "number change"
PURPOSE_SIGNATURE = "signature"


def is_production():
    return os.environ.get("NIVARA_ENV", "development").strip().lower() == "production"


def _now():
    return datetime.now(timezone.utc)


def json_object():
    """The request body as a JSON object; anything else is treated as empty."""
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def text_field(payload, key, default=""):
    """A string field from a JSON body. Any other type is a client error."""
    value = payload.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise BadRequest(f"{key} must be text.")
    return value


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def _load_secret():
    """
    NIVARA_JWT_SECRET from the environment, or a random secret generated once
    and kept in backend/.jwt_secret (git-ignored). Persisting it means the
    Flask reloader does not sign everyone out on every code change.
    """
    secret = os.environ.get("NIVARA_JWT_SECRET")
    if secret:
        return secret
    if is_production():
        raise RuntimeError("NIVARA_JWT_SECRET must be set when NIVARA_ENV=production.")
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    secret = secrets.token_urlsafe(48)
    fd = os.open(SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(secret)
    return secret


def init_app(app):
    app.config.update(
        JWT_SECRET_KEY=_load_secret(),
        JWT_TOKEN_LOCATION=["cookies"],
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=ACCESS_TOKEN_MINUTES),
        JWT_ACCESS_COOKIE_PATH="/api/",
        JWT_COOKIE_CSRF_PROTECT=True,
        JWT_COOKIE_SAMESITE=os.environ.get("NIVARA_COOKIE_SAMESITE", "Lax"),
        # Must be "1" whenever the site is served over HTTPS.
        JWT_COOKIE_SECURE=os.environ.get("NIVARA_COOKIE_SECURE", "0") == "1",
    )
    jwt.init_app(app)
    app.register_blueprint(bp)
    app.after_request(_refresh_expiring_token)


@jwt.user_lookup_loader
def _load_user(_header, payload):
    user = db.get_user(int(payload["sub"]))
    return user if user and user["active"] else None


@jwt.token_in_blocklist_loader
def _session_revoked(_header, payload):
    """
    Server-side revocation for otherwise stateless tokens. A token stops
    working when it was signed out, when its account's token_version has
    moved on (password reset, deactivation, phone recovery), or when the
    original sign-in is older than MAX_SESSION_HOURS.
    """
    try:
        user = db.get_user(int(payload["sub"]))
    except (KeyError, TypeError, ValueError):
        return True
    if user is None or payload.get("ver") != user.get("token_version", 0):
        return True
    auth_time = payload.get("auth_time")
    if not isinstance(auth_time, (int, float)):
        return True
    if _now() - datetime.fromtimestamp(auth_time, timezone.utc) > timedelta(hours=MAX_SESSION_HOURS):
        return True
    return db.is_token_revoked(payload.get("jti"))


def _auth_error(message, status=401):
    return jsonify({"error": message, "code": "AUTH_REQUIRED"}), status


@jwt.revoked_token_loader
def _revoked_token(_header, _payload):
    return _auth_error("Your session has ended. Please sign in again.")


def _issue_token(user, auth_time=None):
    claims = {
        "ver": user.get("token_version", 0),
        "auth_time": int(auth_time if auth_time is not None else _now().timestamp()),
    }
    return create_access_token(identity=str(user["id"]), additional_claims=claims)


def end_other_sessions(user_id):
    """Invalidate every token issued so far for this account."""
    db.bump_token_version(user_id)


@jwt.unauthorized_loader
def _missing_token(_reason):
    return _auth_error("Please sign in to continue.")


@jwt.invalid_token_loader
def _invalid_token(_reason):
    return _auth_error("Your session is invalid. Please sign in again.")


@jwt.expired_token_loader
def _expired_token(_header, _payload):
    return _auth_error("Your session has expired. Please sign in again.")


@jwt.user_lookup_error_loader
def _unknown_user(_header, _payload):
    return _auth_error("This account is no longer active.")


def _refresh_expiring_token(response):
    """
    Sliding session: when a request arrives with a token that is close to
    expiring, send back a fresh one. The new CSRF token is returned in a
    header so the frontend can pick it up without reading cookies.
    """
    try:
        claims = get_jwt()
        exp = claims["exp"]
    except (RuntimeError, KeyError):
        return response  # no authenticated request in this context
    if response.status_code >= 400 or getattr(response, "nivara_session_closed", False):
        return response
    remaining = datetime.fromtimestamp(exp, timezone.utc) - datetime.now(timezone.utc)
    if remaining < timedelta(minutes=REFRESH_WINDOW_MINUTES):
        user = db.get_user(int(get_jwt_identity()))
        if user is None or not user["active"]:
            return response
        token = _issue_token(user, auth_time=claims.get("auth_time"))
        set_access_cookies(response, token)
        response.headers["X-CSRF-TOKEN"] = get_csrf_token(token)
    return response


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

def role_required(*roles):
    """Allow the request only for a signed-in user whose role is in roles."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            if current_user["role"] not in roles:
                return jsonify({"error": "You do not have permission to do this."}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def public_user(user):
    return {
        "id": user["id"],
        "username": user.get("username"),
        "email": user["email"],
        "phone": user.get("phone"),
        "name": user["name"],
        "role": user["role"],
        "unit": user.get("unit"),
        "station": user.get("station"),
        "availability": user.get("availability"),
        "capacity": user.get("capacity"),
    }


def _session_response(user, status=200):
    token = _issue_token(user)
    db.touch_last_login(user["id"])
    response = jsonify({"user": public_user(user), "csrf_token": get_csrf_token(token)})
    set_access_cookies(response, token)
    return response, status


def _client_ip():
    # request.remote_addr is the direct peer. If NIVARA is ever deployed
    # behind a reverse proxy, wrap the app in werkzeug's ProxyFix so this
    # reflects the real client rather than the proxy.
    return request.remote_addr or "unknown"


def _normalise_email(value):
    return value.strip().lower() if isinstance(value, str) else ""


def normalise_mobile(value):
    """
    Indian mobile number in E.164 form (+91XXXXXXXXXX), or None if invalid.
    Accepts 9876543210, 09876543210, +91 98765 43210, 91-98765-43210 and
    similar.
    """
    if not isinstance(value, str):
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return f"+91{digits}" if INDIAN_MOBILE_RE.match(digits) else None


def _parse_identifier(payload):
    """
    Read the sign-in channel and address from a request body.
    Returns (channel, identifier) or (channel, None) if the address is invalid.
    Older clients send only {"email": ...}, which is treated as the email channel.
    """
    channel = payload.get("channel") or ("email" if "email" in payload else None)
    if channel not in ("sms", "email"):
        return None, None
    raw = payload.get("identifier") if "identifier" in payload else payload.get("email")
    if channel == "sms":
        return channel, normalise_mobile(raw)
    if channel == "email":
        email = _normalise_email(raw)
        return channel, email if EMAIL_RE.match(email) else None
    return None, None


# ---------------------------------------------------------------------------
# Staff sign-in (password)
# ---------------------------------------------------------------------------

@bp.route("/login", methods=["POST"])
def login():
    """Staff sign-in. Accepts a username or an email address."""
    payload = json_object()
    handle = _normalise_email(payload.get("username") or payload.get("email"))
    password = payload.get("password")
    password = password if isinstance(password, str) else ""
    ip = _client_ip()

    if not handle or not password:
        return jsonify({"error": "Username and password are required."}), 400

    if (db.count_attempts("login_fail", handle, RATE_WINDOW_SECONDS) >= LOGIN_MAX_FAILS_PER_EMAIL
            or db.count_attempts("login_fail", ip, RATE_WINDOW_SECONDS) >= LOGIN_MAX_FAILS_PER_IP):
        return jsonify({"error": "Too many failed attempts. Try again in 15 minutes."}), 429

    user = db.get_user_by_login(name_or_email=handle)
    stored_hash = user["password_hash"] if user and user["password_hash"] else _DUMMY_HASH
    # Always run the hash check, so an unknown username takes as long as a
    # wrong password and response timing does not reveal which accounts exist.
    password_ok = check_password_hash(stored_hash, password)
    valid = (
        user is not None
        and user["role"] in STAFF_ROLES
        and user["active"]
        and bool(user["password_hash"])
        and password_ok
    )
    if not valid:
        db.record_attempt("login_fail", handle)
        db.record_attempt("login_fail", ip)
        # Same message whether the username or the password was wrong.
        return jsonify({"error": "Incorrect username or password."}), 401

    db.clear_attempts("login_fail", handle)
    return _session_response(user)


# ---------------------------------------------------------------------------
# Citizen sign-in (one-time code by email or SMS)
# ---------------------------------------------------------------------------

def _hash_code(identifier, code, purpose=PURPOSE_SIGN_IN):
    key = current_app.config["JWT_SECRET_KEY"].encode()
    return hmac.new(key, f"{purpose}:{identifier}:{code}".encode(), hashlib.sha256).hexdigest()


class DeliveryUnavailable(OSError):
    """No real delivery channel is configured and console delivery is not allowed."""


def _print_code(identifier, code, how):
    print(f"\n[NIVARA dev] Sign-in code for {identifier}: {code} "
          f"(valid {CODE_TTL_MINUTES} min; {how})\n", flush=True)


def _console_delivery(identifier, code, how):
    # Printing codes is for local development only. In production a missing
    # SMTP or SMS configuration must fail closed, never leak codes into logs.
    if is_production():
        raise DeliveryUnavailable("No delivery channel configured for one-time codes.")
    _print_code(identifier, code, how)


def _send_email_code(email, code):
    """
    Send the code by SMTP when SMTP_HOST is configured. Otherwise print it to
    the backend console, which is how codes are read during local
    development and the demo.
    """
    host = os.environ.get("SMTP_HOST")
    if not host:
        _console_delivery(email, code, "set SMTP_HOST to send real email")
        return

    msg = EmailMessage()
    msg["Subject"] = "Your NIVARA sign-in code"
    msg["From"] = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER", "")
    msg["To"] = email
    msg.set_content(
        f"Your NIVARA sign-in code is {code}.\n\n"
        f"It expires in {CODE_TTL_MINUTES} minutes. If you did not request it, "
        f"you can ignore this email."
    )
    port = int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        smtp.starttls()
        user = os.environ.get("SMTP_USER")
        if user:
            smtp.login(user, os.environ.get("SMTP_PASSWORD", ""))
        smtp.send_message(msg)


def _send_sms_code(phone, code):
    """
    Send the code by SMS when SMS_PROVIDER=twilio is configured. Otherwise
    print it to the backend console.

    Commercial SMS to Indian numbers must go through a sender registered on
    TRAI's DLT platform, so console delivery is the default for the prototype.
    """
    if os.environ.get("SMS_PROVIDER", "console").lower() != "twilio":
        _console_delivery(phone, code, "set SMS_PROVIDER=twilio to send real SMS")
        return

    sid = os.environ["TWILIO_ACCOUNT_SID"]
    token = os.environ["TWILIO_AUTH_TOKEN"]
    body = urllib.parse.urlencode({
        "From": os.environ["TWILIO_FROM_NUMBER"],
        "To": phone,
        "Body": f"Your NIVARA sign-in code is {code}. It expires in {CODE_TTL_MINUTES} minutes.",
    }).encode()
    req = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        data=body,
        headers={"Authorization": "Basic " + base64.b64encode(f"{sid}:{token}".encode()).decode()},
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        json.loads(res.read() or b"{}")


def issue_code(identifier, channel, purpose=PURPOSE_SIGN_IN):
    """
    Generate a one-time code, store its hash and send it. Shared by sign-in,
    changing a mobile number, and signing a complaint digitally. A code only
    works for the purpose it was issued for.
    """
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.store_login_code(identifier, channel, _hash_code(identifier, code, purpose), CODE_TTL_MINUTES, purpose)
    if channel == "sms":
        _send_sms_code(identifier, code)
    else:
        _send_email_code(identifier, code)
    return code


def too_many_wrong_codes(identifier):
    return db.count_attempts("otp_fail", identifier, OTP_FAIL_WINDOW_SECONDS) >= OTP_FAIL_LIMIT


def match_code(identifier, channel, code, purpose):
    """
    The active code record if `code` is right for this address and purpose,
    else None. A wrong guess counts against the code and against the address.
    Does not consume the code.
    """
    if not isinstance(code, str) or not re.fullmatch(r"\d{6}", code):
        return None
    if too_many_wrong_codes(identifier):
        return None
    record = db.get_active_login_code(identifier, purpose)
    if record is None or record["attempts"] >= CODE_MAX_ATTEMPTS or record["channel"] != channel:
        return None
    if not hmac.compare_digest(record["code_hash"], _hash_code(identifier, code, purpose)):
        db.bump_code_attempts(record["id"])
        db.record_attempt("otp_fail", identifier)
        return None
    return record


def check_code(identifier, channel, code, purpose):
    """Verify a one-time code and consume it. Returns True on success."""
    record = match_code(identifier, channel, code, purpose)
    if record is None:
        return False
    db.consume_login_code(record["id"])
    db.clear_attempts("otp_fail", identifier)
    return True


def throttled(identifier, ip, kind="code_request"):
    """
    Rate limits for anything that sends a code. Returns an error response, or
    None if the request is allowed.

    Counted per purpose (`kind`), so that signing in, changing a number and
    signing a complaint do not block one another: a citizen who has just
    signed in can still sign their complaint straight away. The per-IP limit
    is shared across purposes, so the overall cost of sending messages stays
    capped.
    """
    if db.count_attempts(kind, identifier, CODE_RESEND_COOLDOWN_SECONDS) > 0:
        return jsonify({"error": "Please wait a minute before requesting another code."}), 429
    if (db.count_attempts(kind, identifier, RATE_WINDOW_SECONDS) >= CODE_MAX_PER_IDENTIFIER
            or db.count_attempts("code_request_ip", ip, RATE_WINDOW_SECONDS) >= CODE_MAX_PER_IP):
        return jsonify({"error": "Too many codes requested. Try again in 15 minutes."}), 429
    db.record_attempt(kind, identifier)
    db.record_attempt("code_request_ip", ip)
    return None


def _find_citizen_login(channel, identifier):
    if channel == "sms":
        return db.get_user_by_login(phone=identifier)
    return db.get_user_by_login(email=identifier)


@bp.route("/otp/request", methods=["POST"])
def request_code():
    payload = json_object()
    channel, identifier = _parse_identifier(payload)
    ip = _client_ip()

    if channel is None:
        return jsonify({"error": "Choose email or mobile number."}), 400
    if identifier is None:
        return jsonify({"error": "Enter a valid 10-digit Indian mobile number."
                        if channel == "sms" else "Enter a valid email address."}), 400

    limited = throttled(identifier, ip)
    if limited:
        return limited

    existing = _find_citizen_login(channel, identifier)
    # Staff accounts must use their password; a code would bypass it. The
    # response is identical either way so it reveals nothing about the account.
    if existing is None or (existing["role"] == "citizen" and existing["active"]):
        try:
            issue_code(identifier, channel)
        except (smtplib.SMTPException, OSError, urllib.error.URLError, KeyError, ValueError):
            current_app.logger.exception("Could not send sign-in code")
            return jsonify({"error": "We could not send the code. Please try again."}), 502

    return jsonify({
        "message": "If this can be used to sign in, a code has been sent.",
        "identifier": identifier,
        "expires_in_minutes": CODE_TTL_MINUTES,
    }), 200


@bp.route("/otp/verify", methods=["POST"])
def verify_code():
    payload = json_object()
    channel, identifier = _parse_identifier(payload)
    code = re.sub(r"\s", "", text_field(payload, "code"))
    name = text_field(payload, "name").strip()
    contact = (text_field(payload, "contact") or text_field(payload, "phone")).strip()

    invalid = (jsonify({"error": "That code is incorrect or has expired."}), 400)
    if identifier is None or not re.fullmatch(r"\d{6}", code):
        return invalid
    if too_many_wrong_codes(identifier):
        return jsonify({"error": "Too many incorrect codes for this address. Try again in a few hours, "
                                 "or visit your police station."}), 429

    record = match_code(identifier, channel, code, PURPOSE_SIGN_IN)
    if record is None:
        return invalid

    user = _find_citizen_login(channel, identifier)
    if user is not None and (user["role"] != "citizen" or not user["active"]):
        return invalid

    if user is None:
        # First sign-in: the code is valid, but a name is needed before the
        # account is created. The code is not consumed, so it can be resubmitted.
        if len(name) < 2:
            return jsonify({
                "error": "Enter your full name to finish creating your account.",
                "code": "NAME_REQUIRED",
            }), 400
        if len(name) > 120:
            return jsonify({"error": "Name is too long."}), 400

        # The other contact detail is optional and unverified, so it is kept
        # as contact information only, never as a way to sign in.
        contact_email = contact_phone = None
        if contact:
            if channel == "sms":
                contact_email = _normalise_email(contact)
                if not EMAIL_RE.match(contact_email):
                    return jsonify({"error": "Enter a valid email address, or leave it blank."}), 400
            else:
                contact_phone = normalise_mobile(contact)
                if contact_phone is None:
                    return jsonify({"error": "Enter a valid 10-digit mobile number, or leave it blank."}), 400

        db.create_user(
            identifier if channel == "email" else None,
            name,
            "citizen",
            phone=identifier if channel == "sms" else None,
            contact_email=contact_email,
            contact_phone=contact_phone,
        )
        user = _find_citizen_login(channel, identifier)

    db.consume_login_code(record["id"])
    db.clear_attempts("otp_fail", identifier)
    return _session_response(user)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

@bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    return jsonify({
        "user": public_user(current_user),
        "csrf_token": get_jwt().get("csrf"),
    }), 200


@bp.route("/logout", methods=["POST"])
def logout():
    # Revoke the presented token server-side, so a copied cookie stops working
    # too. An absent, expired or already revoked token still signs out.
    try:
        verify_jwt_in_request(optional=True)
        claims = get_jwt()
    except Exception:
        claims = {}
    if claims.get("jti"):
        db.revoke_token(claims["jti"], claims.get("exp"))
    response = jsonify({"message": "Signed out."})
    response.nivara_session_closed = True
    unset_jwt_cookies(response)
    return response, 200


# ---------------------------------------------------------------------------
# Changing the mobile number on an account
# ---------------------------------------------------------------------------
#
# The account is the identity, not the number. A citizen verifies the new
# number while signed in on the old one, and their complaints stay with them.
# The released number no longer opens the account, so whoever is issued it
# next starts with an empty one.

@bp.route("/phone/change/request", methods=["POST"])
@role_required("citizen")
def request_phone_change():
    payload = json_object()
    new_phone = normalise_mobile(payload.get("phone"))
    if new_phone is None:
        return jsonify({"error": "Enter a valid 10-digit Indian mobile number."}), 400
    if new_phone == current_user.get("phone"):
        return jsonify({"error": "That is already the number on your account."}), 400

    # Throttle before looking the number up, and answer the same way whether
    # or not it belongs to someone else: otherwise any signed-in citizen could
    # test which numbers have filed complaints with the police.
    limited = throttled(new_phone, _client_ip(), kind="phone_change")
    if limited:
        return limited
    if db.get_user_by_login(phone=new_phone) is None:
        try:
            issue_code(new_phone, "sms", purpose=PURPOSE_NUMBER_CHANGE)
        except (OSError, urllib.error.URLError, KeyError, ValueError):
            current_app.logger.exception("Could not send number-change code")
            return jsonify({"error": "We could not send the code. Please try again."}), 502
    return jsonify({
        "message": "If this number can be added to your account, we sent a code to it.",
        "phone": new_phone,
    }), 200


@bp.route("/phone/change/verify", methods=["POST"])
@role_required("citizen")
def verify_phone_change():
    payload = json_object()
    new_phone = normalise_mobile(payload.get("phone"))
    code = re.sub(r"\s", "", text_field(payload, "code"))
    invalid = (jsonify({"error": "That code is incorrect or has expired."}), 400)
    if new_phone is None or not check_code(new_phone, "sms", code, PURPOSE_NUMBER_CHANGE):
        return invalid
    try:
        old = db.change_phone(current_user["id"], new_phone, current_user["id"], "Changed by the citizen")
    except sqlite3.IntegrityError:
        return invalid
    # Sign out every other session on the account; this one gets a new token.
    end_other_sessions(current_user["id"])
    user = db.get_user(current_user["id"])
    token = _issue_token(user)
    response = jsonify({
        "user": public_user(user),
        "previous_phone": old,
        "csrf_token": get_csrf_token(token),
        "message": "Your number has been updated. Your complaints stay on this account.",
    })
    response.nivara_session_closed = True
    set_access_cookies(response, token)
    response.headers["X-CSRF-TOKEN"] = get_csrf_token(token)
    return response, 200
