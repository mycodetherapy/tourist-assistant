"""Лёгкий mail notify из Python worker (Resend HTTP или log)."""

from __future__ import annotations

import json
import logging
import os
import urllib.request

logger = logging.getLogger(__name__)


def _send_resend(*, to: str, subject: str, text: str, html: str) -> None:
    api_key = (os.getenv("RESEND_API_KEY") or "").strip()
    from_addr = (os.getenv("MAIL_FROM") or "Прогуляй <noreply@progulyai.ru>").strip()
    if not api_key:
        logger.info("mailer:dev to=%s subject=%s\n%s", to, subject, text)
        return
    body = json.dumps(
        {
            "from": from_addr,
            "to": [to],
            "subject": subject,
            "text": text,
            "html": html,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"Resend HTTP {resp.status}")


def notify_osrm_prepare_result(
    *,
    user_id: int,
    city_name: str,
    ok: bool,
    error: str | None = None,
) -> None:
    try:
        from db.postgres.osrm_prepare_jobs import get_user_email

        email = get_user_email(user_id)
        if not email or email.endswith("@guest.progulyai.local"):
            return
        if ok:
            subject = f"Город {city_name} готов на карте — Прогуляй"
            text = f"Пеший граф для «{city_name}» готов."
            html = f"<p>Пеший граф для <strong>{city_name}</strong> готов.</p>"
        else:
            subject = f"Не удалось подготовить {city_name} — Прогуляй"
            text = f"Подготовка «{city_name}» не удалась. {error or ''}".strip()
            html = (
                f"<p>Подготовка <strong>{city_name}</strong> не удалась.</p>"
                + (f"<p>{error}</p>" if error else "")
            )
        _send_resend(to=email, subject=subject, text=text, html=html)
    except Exception:
        logger.warning("notify_osrm_prepare_result failed", exc_info=True)
