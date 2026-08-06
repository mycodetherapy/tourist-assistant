"""OSRM HTTP-клиент: пешая геометрия маршрута для TripRouteCase."""

from __future__ import annotations

from search.osrm.client import OsrmRouteResult, fetch_foot_route

__all__ = ["OsrmRouteResult", "fetch_foot_route"]
