#!/usr/bin/env python3
"""Генерация фрагмента docker-compose для osrm-{slug} из city_packs.yaml."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.city_catalog import load_city_pack_specs

PORT_BASE = 5002


def main() -> int:
    lines = ["# Auto-generated OSRM city services (scripts/compose_osrm_city.py)\n"]
    for idx, spec in enumerate(load_city_pack_specs().values()):
        port = PORT_BASE + idx
        slug = spec.slug
        lines.append(f"  {spec.osrm_service}:")
        lines.append(f"    profiles: [routing, {spec.compose_profile}]")
        lines.append("    image: ghcr.io/project-osrm/osrm-backend:latest")
        lines.append(
            f"    command: osrm-routed --algorithm mld /data/{spec.osrm_base_name}.osrm"
        )
        lines.append(f"    volumes:")
        lines.append(f"      - ./data/cities/{slug}/osrm:/data")
        lines.append(f"    ports:")
        lines.append(f'      - "${{OSRM_{slug.upper().replace("-", "_")}_HOST_PORT:-{port}}}:5000"')
        lines.append("    restart: unless-stopped")
        lines.append("")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
