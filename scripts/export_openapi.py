"""Экспорт OpenAPI 3 из api-node (Fastify @fastify/swagger) в docs/openapi.json."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "openapi.json"
API_NODE = ROOT / "api-node"


def export_openapi(*, output: Path = OUTPUT) -> Path:
    """Генерирует схему из зарегистрированных маршрутов api-node."""
    if not (API_NODE / "package.json").is_file():
        raise SystemExit(f"api-node not found: {API_NODE}")
    subprocess.run(
        ["npm", "run", "export:openapi"],
        cwd=API_NODE,
        check=True,
    )
    if not output.is_file():
        raise SystemExit(f"Export failed: {output} not created")
    return output


def main() -> None:
    path = export_openapi()
    print(f"OpenAPI exported: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
