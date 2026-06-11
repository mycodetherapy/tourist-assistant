"""Partner Links API Travelpayouts."""

from __future__ import annotations

from typing import Iterable

import requests

from search.affiliate.config import (
    affiliate_api_token,
    affiliate_marker,
    affiliate_trs,
    partner_links_available,
)

LINKS_API_URL = "https://api.travelpayouts.com/links/v1/create"
LINKS_TIMEOUT = 15


class PartnerLinksError(RuntimeError):
    pass


def create_partner_links(
    links: Iterable[tuple[str, str]],
    *,
    shorten: bool = False,
) -> dict[str, str]:
    """
    Преобразует исходные URL в partner_url.
    links: (url, sub_id) → dict[url, partner_url].
    """
    if not partner_links_available():
        return {}

    trs = affiliate_trs()
    marker = affiliate_marker()
    token = affiliate_api_token()
    if trs is None or not marker or not token:
        return {}

    payload_links = [{"url": url, "sub_id": sub_id} for url, sub_id in links]
    if not payload_links:
        return {}

    body = {
        "trs": trs,
        "marker": int(marker) if marker.isdigit() else marker,
        "shorten": shorten,
        "links": payload_links,
    }
    try:
        response = requests.post(
            LINKS_API_URL,
            json=body,
            headers={
                "X-Access-Token": token,
                "Content-Type": "application/json",
            },
            timeout=LINKS_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"  → affiliate Links API: ошибка ({exc})")
        return {}

    if not isinstance(data, dict):
        return {}

    out: dict[str, str] = {}
    for item in data.get("links") or []:
        if not isinstance(item, dict):
            continue
        if item.get("code") != "success":
            continue
        src = str(item.get("url") or "")
        partner = str(item.get("partner_url") or "").strip()
        if src and partner:
            out[src] = partner
    return out
