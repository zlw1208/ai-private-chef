FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
RUN --mount=type=cache,target=/root/.cache/pip \
    mkdir -p backend \
    && touch backend/__init__.py \
    && pip install ".[agent,sqlite,postgres,oss]" \
    && rm -rf backend ai_private_chef.egg-info build

COPY backend ./backend
COPY frontend ./frontend
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-deps .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
