"""Фоновая генерация факта о городе (параллельно с маршрутами)."""

from __future__ import annotations

import threading
from typing import Any

from agents.city_fact import generate_city_fact
from agents.llm_context import LlmConfig, run_with_llm_config
from db.repository import patch_itinerary_program

__all__ = ["schedule_city_fact_generation"]


def schedule_city_fact_generation(
    *,
    trip_id: int,
    city: str,
    version_id: int | None,
    llm_config: LlmConfig,
    version_event: threading.Event | None = None,
    version_holder: dict[str, Any] | None = None,
) -> None:
    """
    Запускает daemon-поток: ждёт version_id (если нужно), генерирует факт, патчит program.
    """

    def _worker() -> None:
        target_version = version_id
        if target_version is None and version_event is not None and version_holder is not None:
            version_event.wait(timeout=600)
            target_version = version_holder.get("version_id")
        if not target_version:
            return
        try:
            with run_with_llm_config(llm_config):
                fact = generate_city_fact(city=city, use_llm=True)
            patch_itinerary_program(
                int(target_version),
                {"lifehacks": fact, "city_fact_status": "ready"},
            )
            print(f"  [city_fact] trip #{trip_id} version #{target_version} ready")
        except Exception as exc:
            patch_itinerary_program(
                int(target_version),
                {"city_fact_status": "failed"},
            )
            print(f"  [city_fact] trip #{trip_id} failed: {exc}")

    thread = threading.Thread(target=_worker, daemon=True, name=f"city-fact-{trip_id}")
    thread.start()
