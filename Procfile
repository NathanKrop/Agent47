web: uvicorn dashboard.app:app --host 0.0.0.0 --port $PORT
agent: python -m scheduler.main_pipeline
worker: celery -A scheduler.worker worker --concurrency=4 --loglevel=info
