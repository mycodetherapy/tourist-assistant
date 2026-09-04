# Python worker (LangGraph) + Alembic
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Self-serve OSRM: docker CLI + curl (fo_ensure / Geofabrik) + pyosmium runtime
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
       docker.io bash ca-certificates curl libexpat1 \
  && rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["python", "-m", "worker"]
