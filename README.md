# LLM/SLM Evaluation Platform

SQLite-first implementation of the API-hosted model evaluation platform described in `docs/`.

## Current increment

The service initializes a local SQLite database automatically and exposes a health endpoint. Model endpoint management and evaluation runs are the next increments.

## Run locally

```powershell
python -m pip install -e ".[dev]"
uvicorn app.main:app --app-dir backend --reload
```

The default database is `data/llm_evaluation.db`. Override it with `LLE_DATABASE_URL`, for example:

```powershell
$env:LLE_DATABASE_URL = "sqlite:///C:/temp/llm_evaluation.db"
```

Open `http://127.0.0.1:8000/docs` for the API and `http://127.0.0.1:8000/health` for the health check.
