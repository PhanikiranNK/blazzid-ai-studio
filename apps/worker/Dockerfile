FROM python:3.9-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY packages/ packages/
COPY apps/worker/ apps/worker/
COPY alembic.ini .

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
      "sqlalchemy>=2.0.25" "alembic>=1.13.0" "redis>=5.0.0" "psycopg[binary]>=3.1.0" \
      "numpy>=1.24.0" "opencv-python-headless>=4.8.0" && \
    pip install --no-cache-dir \
      -e packages/core \
      -e packages/algorithms \
      -e packages/media \
      -e packages/detection \
      -e packages/assembly \
      -e packages/storage \
      -e packages/jobs \
      -e apps/worker

CMD ["python", "-m", "blazzid_worker.main"]
