FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

FROM python:3.12-slim AS runtime

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app

COPY --from=builder /usr/local /usr/local
COPY app/ /app/app/
COPY scripts/ /app/scripts/
COPY alembic.ini /app/alembic.ini
COPY alembic/ /app/alembic/
COPY CHANGELOG.md /app/CHANGELOG.md
WORKDIR /app
RUN mkdir -p /app/storage && chown -R 10001:10001 /app

ENV PORT=8000 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER 10001
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
