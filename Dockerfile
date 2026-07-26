FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY backend ./backend
RUN pip install --no-cache-dir ".[postgresql]"

ENV PYTHONPATH=/app/backend
ENV LLE_DATA_ROOT=/data
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
