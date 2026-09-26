FROM python:3.13-slim

WORKDIR /app

# Copy shared package first (models/session used by normalize.py)
COPY shared/ /app/shared/
COPY ingestion-service/requirements.txt /app/requirements.txt
COPY shared/db/requirements.txt /app/shared-db-requirements.txt

RUN pip install --no-cache-dir -r requirements.txt -r shared-db-requirements.txt

COPY ingestion-service/app/ /app/app/

ENTRYPOINT ["python", "-m", "app.main"]
CMD ["--source", "internshala"]