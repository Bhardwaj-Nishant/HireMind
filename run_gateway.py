"""
Root-level runner for gateway-service — ensures both `gateway-service/`
(for the `app` package) and the repo root (for `shared`) are on the path
before starting uvicorn. Same reasoning as run_ingestion.py/run_matching.py.

Run from the hiremind/ repo root:
    python run_gateway.py
"""
import sys

import uvicorn

sys.path.insert(0, "gateway-service")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)