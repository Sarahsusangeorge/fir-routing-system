/**
 * Reference catalog used by the local (demo-mode) classification engine.
 * Mirrors the rule tables that the real Priority Engine / Routing Engine
 * would apply server-side — kept here only so the frontend remains fully
 * demonstrable when the backend is unavailable.
 */

export interface LegalCategory {
  code: string;
  title: string;
  keywords: string[];
  /** Relative severity, 0–10, used as an input to the priority score. */
  severity: number;
  unit: string;
  reason: string;
}

export const LEGAL_CATALOG: LegalCategory[] = [
  {
    code: "302",
    title: "Murder",
    keywords: ["murder", "murdered", "killed", "kill", "fatally", "fatal", "strangled", "stabbed to death"],
    severity: 9.4,
    unit: "Crime Branch",
    reason: "Section 302 is cognizable and non-bailable.",
  },
  {
    code: "307",
    title: "Attempt to Murder",
    keywords: ["attempt to murder", "attempted to kill", "tried to kill", "shot at", "stabbed"],
    severity: 8.8,
    unit: "Crime Branch",
    reason: "Section 307 involves grievous intent and is treated as a serious cognizable offence.",
  },
  {
    code: "392",
    title: "Robbery",
    keywords: ["robbed", "robbery", "looted", "snatched at knifepoint", "armed robbery"],
    severity: 7.6,
    unit: "Crime Branch",
    reason: "Section 392 (Robbery) is cognizable and requires immediate investigation.",
  },
  {
    code: "363",
    title: "Kidnapping",
    keywords: ["kidnap", "kidnapped", "abducted", "abduction", "forcibly taken"],
    severity: 8.7,
    unit: "Crime Branch",
    reason: "Section 363 (Kidnapping) mandates urgent inter-jurisdictional coordination.",
  },
  {
    code: "147",
    title: "Rioting",
    keywords: ["mob", "rioting", "unlawful assembly", "group of men attacked", "armed with sticks"],
    severity: 6.4,
    unit: "Crime Branch",
    reason: "Section 147 offences involving unlawful assembly are escalated to the Crime Branch.",
  },
  {
    code: "379",
    title: "Theft",
    keywords: ["stole", "theft", "stolen", "snatched", "pickpocket"],
    severity: 3.8,
    unit: "Local Police Station",
    reason: "Section 379 (Theft) is handled at the jurisdictional station level.",
  },
  {
    code: "323",
    title: "Voluntarily Causing Hurt",
    keywords: ["hit", "beaten", "assaulted", "punched", "hurt"],
    severity: 3.4,
    unit: "Local Police Station",
    reason: "Section 323 (Voluntarily Causing Hurt) is a bailable offence handled locally.",
  },
  {
    code: "324",
    title: "Hurt by Dangerous Weapon",
    keywords: ["weapon", "knife", "blade", "sharp object", "rod"],
    severity: 5.6,
    unit: "Local Police Station",
    reason: "Section 324 applies when a weapon is used and is monitored at the station level.",
  },
  {
    code: "498A",
    title: "Cruelty by Husband or Relatives",
    keywords: ["dowry", "in-laws", "matrimonial cruelty", "harassed by her husband", "harassed for dowry"],
    severity: 6.9,
    unit: "Women's Cell",
    reason: "Section 498A cases are routed to the Women's Cell for sensitive handling.",
  },
  {
    code: "354A",
    title: "Sexual Harassment",
    keywords: ["harassed", "inappropriate", "workplace harassment", "molested", "unwelcome advances"],
    severity: 6.6,
    unit: "Women's Cell",
    reason: "Section 354A offences are directed to the Women's Cell.",
  },
  {
    code: "354D",
    title: "Stalking",
    keywords: ["stalking", "followed her", "unwanted messages", "repeatedly followed"],
    severity: 5.7,
    unit: "Women's Cell",
    reason: "Section 354D (Stalking) is routed to the Women's Cell for continued monitoring.",
  },
  {
    code: "420",
    title: "Cheating",
    keywords: ["cheated", "fraud", "duped", "fake investment", "ponzi"],
    severity: 5.1,
    unit: "Economic Offences Wing",
    reason: "Section 420 (Cheating) is routed to the Economic Offences Wing for financial investigation.",
  },
  {
    code: "465",
    title: "Forgery",
    keywords: ["forged", "fake signature", "counterfeit document", "forged documents"],
    severity: 4.7,
    unit: "Economic Offences Wing",
    reason: "Section 465 (Forgery) requires document verification by the Economic Offences Wing.",
  },
  {
    code: "66C",
    title: "Identity Theft (IT Act)",
    keywords: ["identity theft", "stole my identity", "impersonated", "fake profile"],
    severity: 5.5,
    unit: "Cyber Cell",
    reason: "Offences under the IT Act are routed to the Cyber Cell.",
  },
  {
    code: "66D",
    title: "Cheating by Personation (IT Act)",
    keywords: ["upi", "otp", "phishing", "fraudulent link", "online fraud", "cyber fraud", "bank account was debited"],
    severity: 5.9,
    unit: "Cyber Cell",
    reason: "Section 66D of the IT Act covers cheating by personation using computer resources.",
  },
  {
    code: "506",
    title: "Criminal Intimidation",
    keywords: ["threatened", "intimidated", "threats", "warned to withdraw"],
    severity: 3.1,
    unit: "Local Police Station",
    reason: "Section 506 (Criminal Intimidation) is assessed at the jurisdictional station level.",
  },
  {
    code: "268",
    title: "Public Nuisance",
    keywords: ["noise", "nuisance", "loud music", "disturbance", "encroach"],
    severity: 1.6,
    unit: "Local Police Station",
    reason: "Section 268 (Public Nuisance) is a low-severity civic matter handled locally.",
  },
  {
    code: "NDPS-20",
    title: "Possession of Narcotic Substances",
    keywords: ["drugs", "narcotics", "contraband", "possession of banned substances"],
    severity: 7.2,
    unit: "Anti-Narcotics Cell",
    reason: "Offences under the NDPS Act are routed to the Anti-Narcotics Cell.",
  },
  {
    code: "447",
    title: "Criminal Trespass",
    keywords: ["trespass", "entered the property", "encroached upon", "unauthorized entry"],
    severity: 1.4,
    unit: "Local Police Station",
    reason: "Section 447 (Criminal Trespass) is a minor offence handled at the station level.",
  },
];

export const DEFAULT_CATEGORY: LegalCategory = {
  code: "154",
  title: "General Cognizable Complaint",
  keywords: [],
  severity: 3.0,
  unit: "Local Police Station",
  reason: "No specific statutory pattern was matched; the complaint is routed for preliminary review.",
};

export function priorityLevelFromScore(score: number): "High" | "Medium" | "Low" {
  if (score >= 7) return "High";
  if (score >= 4) return "Medium";
  return "Low";
}
