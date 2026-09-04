"""PBF usability: empty / truncated extracts must not skip osmium extract."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from search.osm.pbf_usable import MIN_PBF_BYTES, is_pbf_usable


class PbfUsableTests(unittest.TestCase):
    def test_missing_file(self) -> None:
        self.assertFalse(is_pbf_usable("/tmp/no-such-extract.osm.pbf", deep=False))

    def test_empty_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".osm.pbf", delete=False) as tmp:
            path = Path(tmp.name)
        try:
            self.assertFalse(is_pbf_usable(path, deep=False))
        finally:
            path.unlink(missing_ok=True)

    def test_too_small(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".osm.pbf", delete=False) as tmp:
            tmp.write(b"OSMHeader" + b"\x00" * 100)
            path = Path(tmp.name)
        try:
            self.assertFalse(is_pbf_usable(path, deep=False))
        finally:
            path.unlink(missing_ok=True)

    def test_header_in_probe_window(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".osm.pbf", delete=False) as tmp:
            tmp.write(b"\x00" * (MIN_PBF_BYTES - 20) + b"OSMHeader" + b"\x00" * 32)
            path = Path(tmp.name)
        try:
            self.assertTrue(is_pbf_usable(path, deep=False))
        finally:
            path.unlink(missing_ok=True)

    def test_no_osm_magic(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".osm.pbf", delete=False) as tmp:
            tmp.write(b"\xff" * MIN_PBF_BYTES)
            path = Path(tmp.name)
        try:
            self.assertFalse(is_pbf_usable(path, deep=False))
        finally:
            path.unlink(missing_ok=True)
