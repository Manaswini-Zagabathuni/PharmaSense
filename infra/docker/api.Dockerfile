FROM python:3.12.10-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system --gid 10001 pharmasense \
    && useradd --system --uid 10001 --gid pharmasense --create-home pharmasense

WORKDIR /app

COPY pyproject.toml requirements-runtime.lock README.md LICENSE ./
COPY packages ./packages
COPY alembic.ini ./
COPY migrations ./migrations

RUN python -m pip install --upgrade "pip==25.0.1" \
    && python -m pip install -r requirements-runtime.lock \
    && python -m pip install --no-deps .

USER pharmasense

EXPOSE 8000

CMD ["sh", "-c", "python -m alembic upgrade head && exec uvicorn pharmasense.api.main:app --host 0.0.0.0 --port 8000"]
