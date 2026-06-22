"""Экспорт OpenAPI: схема API в docs/openapi.json (Node api-node).

После изменений маршрутов api-node обновите docs/openapi.json вручную
или добавьте @fastify/swagger и генерацию из Fastify.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "openapi.json"


def main() -> None:
    if not OUTPUT.is_file():
        print(f"Missing {OUTPUT.relative_to(ROOT)}", file=sys.stderr)
        sys.exit(1)
    print(
        f"OpenAPI: {OUTPUT.relative_to(ROOT)} (static; API — api-node на :8001)"
    )


if __name__ == "__main__":
    main()
