# AIRA API & Worker

FastAPI backend and asynchronous background worker for AIRA Care.

## Local Development

```bash
# Using uv:
uv venv
# On Windows: .venv\Scripts\activate
# On Linux/macOS: source .venv/bin/activate
uv pip install -e ".[dev]"

# Run tests:
pytest -v

# Run API server:
uvicorn app.main:app --reload --port 8000

# Run Worker:
python -m app.worker
```
