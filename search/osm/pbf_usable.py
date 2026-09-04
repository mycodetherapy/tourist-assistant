"""Проверка, что OSM PBF не пустой и не обрезан после OOM."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

MIN_PBF_BYTES = 65_536
_HEADER_PROBE = 65_536


def is_pbf_usable(path: Path | str, *, deep: bool | None = None) -> bool:
    p = Path(path)
    try:
        if not p.is_file() or p.stat().st_size < MIN_PBF_BYTES:
            return False
        head = p.read_bytes()[:_HEADER_PROBE]
    except OSError:
        return False
    if b"OSMHeader" not in head and b"OSMData" not in head:
        return False
    use_osmium = shutil.which("osmium") is not None if deep is None else deep
    if use_osmium:
        osmium = shutil.which("osmium")
        if not osmium:
            return False
        try:
            proc = subprocess.run(
                [osmium, "fileinfo", "-F", "pbf", "-e", str(p)],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        if proc.returncode != 0:
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: python -m search.osm.pbf_usable <file.osm.pbf>", file=sys.stderr)
        return 2
    ok = is_pbf_usable(args[0])
    if not ok:
        print(f"unusable pbf: {args[0]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
