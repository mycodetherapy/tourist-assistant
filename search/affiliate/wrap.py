"""Обёртка markdown и URL билетов в affiliate-ссылки."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from search.affiliate.config import (
    affiliate_aviasales_enabled,
    affiliate_marker,
    partner_links_available,
)
from search.affiliate.links_client import create_partner_links
from search.affiliate.programs import AffiliateProvider, detect_provider, provider_enabled
from search.affiliate.sub_id import build_sub_id

_MARKDOWN_URL = re.compile(r"\]\((https?://[^)]+)\)")


def _append_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query[key] = value
    new_query = urlencode(query)
    return urlunparse(parsed._replace(query=new_query))


def wrap_aviasales_with_marker(url: str) -> str:
    """Fallback без trs: marker в query Aviasales."""
    marker = affiliate_marker()
    if not marker or not affiliate_aviasales_enabled():
        return url
    provider = detect_provider(url)
    if provider is None or provider.key != "aviasales":
        return url
    if "marker=" in url:
        return url
    return _append_query_param(url, "marker", marker)


def _resolve_partner_url(
    url: str,
    *,
    trip_id: int,
    provider: AffiliateProvider,
    partner_batch: dict[str, str],
) -> str:
    sub_id = build_sub_id(trip_id, "tickets", provider)
    if partner_links_available():
        wrapped = partner_batch.get(url)
        if wrapped:
            return wrapped
    if provider.key == "aviasales":
        return wrap_aviasales_with_marker(url)
    return url


def wrap_tickets_markdown(
    markdown: str,
    trip_id: int,
    *,
    itinerary_version_id: int | None = None,
    log_exposure: bool = True,
) -> str:
    """
    Заменяет исходящие URL в markdown билетов на affiliate-версии.
    При log_exposure=True пишет exposure в SQLite (finalize / первое сохранение).
    """
    if not markdown.strip():
        return markdown

    candidates: list[tuple[str, AffiliateProvider]] = []
    seen: set[str] = set()
    for match in _MARKDOWN_URL.finditer(markdown):
        url = match.group(1).strip()
        if url in seen:
            continue
        provider = detect_provider(url)
        if provider is None or not provider_enabled(provider):
            continue
        seen.add(url)
        candidates.append((url, provider))

    if not candidates:
        return markdown

    partner_batch: dict[str, str] = {}
    if partner_links_available():
        partner_batch = create_partner_links(
            (
                (url, build_sub_id(trip_id, "tickets", provider))
                for url, provider in candidates
            )
        )

    replacements: dict[str, str] = {}
    exposures: list[tuple[str, str, str]] = []
    for url, provider in candidates:
        wrapped = _resolve_partner_url(
            url,
            trip_id=trip_id,
            provider=provider,
            partner_batch=partner_batch,
        )
        if wrapped != url:
            replacements[url] = wrapped
            exposures.append(
                (
                    provider.key,
                    provider.label,
                    build_sub_id(trip_id, "tickets", provider),
                )
            )

    if not replacements:
        return markdown

    def _sub(match: re.Match[str]) -> str:
        original = match.group(1)
        return f"]({replacements.get(original, original)})"

    result = _MARKDOWN_URL.sub(_sub, markdown)

    if log_exposure:
        from db.affiliate_repository import log_affiliate_exposure

        for provider_key, provider_label, sub_id in exposures:
            log_affiliate_exposure(
                trip_id,
                channel="tickets",
                provider=provider_key,
                provider_label=provider_label,
                sub_id=sub_id,
                links_count=1,
                itinerary_version_id=itinerary_version_id,
            )

    return result
