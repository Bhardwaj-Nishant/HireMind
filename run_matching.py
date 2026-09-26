"""
Root-level runner for intelligence-service, same reason run_ingestion.py
exists: Python can't import a hyphenated package name directly.

Run from the hiremind/ repo root:
    python run_matching.py match --limit 10
"""
import runpy
import sys

sys.path.insert(0, "intelligence-service")

if __name__ == "__main__":
    sys.argv[0] = "app.main"
    runpy.run_module("app.main", run_name="__main__")