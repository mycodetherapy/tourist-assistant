# Python worker (LangGraph) + Alembic
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Self-serve OSRM: osmium extract в worker (без второго контейнера / 137),
# docker CLI для osrm-backend, curl для fo_ensure, libexpat1 для pyosmium.
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
       docker.io bash ca-certificates curl libexpat1 osmium-tool \
  && rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["python", "-m", "worker"]
