"""fo_ensure.sh: не удаляет старый PBF, пока новая загрузка не прошла проверку."""

from __future__ import annotations

import http.server
import os
import socket
import subprocess
import tempfile
import threading
import unittest
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FO_ENSURE = ROOT / "scripts" / "fo_ensure.sh"
MIN_BYTES = 32
PAYLOAD_OK = b"\xff" * 64
PAYLOAD_OLD = b"\xaa" * 64


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _Handler(http.server.BaseHTTPRequestHandler):
    body = PAYLOAD_OK
    status = 200

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(self.status)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        if self.status == 200:
            self.wfile.write(self.body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def _write_catalog(path: Path, url: str) -> None:
    path.write_text(
        "districts:\n"
        "  testdist:\n"
        "    pbf_name: testdist-latest.osm.pbf\n"
        f"    geofabrik_url: {url}\n"
        f"    min_pbf_bytes: {MIN_BYTES}\n",
        encoding="utf-8",
    )


def _run_ensure(data_dir: Path, catalog: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["TOURIST_DATA_DIR"] = str(data_dir)
    env["FEDERAL_DISTRICTS_YAML"] = str(catalog)
    env["PYTHON"] = os.environ.get("PYTHON") or "python3"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(FO_ENSURE), "testdist"],
        cwd=str(ROOT),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


class FoEnsureAtomicTests(unittest.TestCase):
    def test_keeps_old_file_when_download_fails(self) -> None:
        port = _free_port()
        _Handler.status = 404
        _Handler.body = b"not found"
        server = http.server.ThreadingHTTPServer(("127.0.0.1", port), partial(_Handler))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                data = Path(tmp)
                fo = data / "fo"
                fo.mkdir()
                pbf = fo / "testdist-latest.osm.pbf"
                pbf.write_bytes(PAYLOAD_OLD)
                catalog = data / "districts.yaml"
                _write_catalog(catalog, f"http://127.0.0.1:{port}/missing.osm.pbf")
                result = _run_ensure(data, catalog, {"FORCE_DOWNLOAD": "1"})
                self.assertNotEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertTrue(pbf.is_file())
                self.assertEqual(pbf.read_bytes(), PAYLOAD_OLD)
                self.assertFalse((fo / "testdist-latest.osm.pbf.partial").exists())
        finally:
            _Handler.status = 200
            _Handler.body = PAYLOAD_OK
            server.shutdown()
            server.server_close()

    def test_replaces_file_after_valid_download(self) -> None:
        port = _free_port()
        handler = partial(_Handler)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                data = Path(tmp)
                fo = data / "fo"
                fo.mkdir()
                pbf = fo / "testdist-latest.osm.pbf"
                pbf.write_bytes(PAYLOAD_OLD)
                catalog = data / "districts.yaml"
                _write_catalog(catalog, f"http://127.0.0.1:{port}/testdist-latest.osm.pbf")
                result = _run_ensure(data, catalog, {"FORCE_DOWNLOAD": "1"})
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertEqual(pbf.read_bytes(), PAYLOAD_OK)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
