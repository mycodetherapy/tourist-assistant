"""Экспорт OpenAPI-схемы FastAPI в docs/openapi.json для Swagger и CI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "openapi.json"


def export_openapi(*, output: Path = OUTPUT) -> Path:
    """Генерирует OpenAPI 3 из app.openapi() без запуска lifespan/сервера."""
    sys.path.insert(0, str(ROOT))
    from api.main import app  # noqa: PLC0415

    schema = app.openapi()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(schema, ensure_ascii=False, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    return output


def main() -> None:
    path = export_openapi()
    print(f"OpenAPI exported: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
