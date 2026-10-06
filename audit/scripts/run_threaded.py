"""Run the Flask app with threaded=True on port 5001, to test allocation
under genuine concurrency (the bundled dev server defaults to handling one
request at a time, which masks races in db.allocate()).

Usage: run from (or pass the path to) the repository's backend/ directory:
    python run_threaded.py [path/to/backend]
"""
import os
import sys

backend_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "..", "backend")
sys.path.insert(0, os.path.abspath(backend_dir))
import app as appmod

if __name__ == "__main__":
    appmod.app.run(threaded=True, port=5001, debug=False)
