FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runtime

COPY --from=builder /usr/local /usr/local
COPY app/ /app/app/
COPY alembic.ini /app/alembic.ini
COPY alembic/ /app/alembic/
WORKDIR /app

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
