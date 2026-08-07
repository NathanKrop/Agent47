FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Railway / managed platforms auto-detect the exposed port.
EXPOSE 8000

# Default command = dashboard (web). Railway deploys this as the web service.
# Override per-service for the agent pipeline / Celery worker:
#   python -m scheduler.main_pipeline
#   celery -A scheduler.worker worker --concurrency=8 --loglevel=info
CMD ["uvicorn", "dashboard.app:app", "--host", "0.0.0.0", "--port", "8000"]
