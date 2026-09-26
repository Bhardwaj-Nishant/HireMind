"""
Root-level runner so ingestion-service can be launched without Python
needing to import a hyphenated package name (ingestion-service isn't a
valid Python identifier, so `python -m ingestion-service.app.main` fails).

Run from the hiremind/ repo root:
    python run_ingestion.py --source internshala --max-jobs 5
"""
import runpy
import sys

sys.path.insert(0, "ingestion-service")

if __name__ == "__main__":
    sys.argv[0] = "app.main"
    runpy.run_module("app.main", run_name="__main__")