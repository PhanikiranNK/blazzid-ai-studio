FROM python:3.9-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY packages/ packages/
COPY apps/api/ apps/api/
COPY migrations/ migrations/
COPY alembic.ini .

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
      "fastapi>=0.110.0" "uvicorn>=0.28.0" "python-multipart>=0.0.9" \
      "sqlalchemy>=2.0.25" "alembic>=1.13.0" "redis>=5.0.0" "psycopg[binary]>=3.1.0" && \
    pip install --no-cache-dir -e packages/core -e packages/storage -e packages/jobs -e apps/api

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn blazzid_api.main:app --host 0.0.0.0 --port 8000"]
