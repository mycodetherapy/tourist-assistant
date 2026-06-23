#!/usr/bin/env python3
"""Запуск OSRM gateway (uvicorn)."""

from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "services.osrm_gateway.app:app",
        host=os.getenv("OSRM_GATEWAY_HOST", "0.0.0.0"),
        port=int(os.getenv("OSRM_GATEWAY_PORT", "8080")),
        log_level="info",
    )
