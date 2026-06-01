"""Resolve which collision-regs regime applies at a position via point-in-polygon."""

from __future__ import annotations


def _point_in_ring(lon: float, lat: float, ring: list) -> bool:
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        if (y1 > lat) != (y2 > lat):
            x_at = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < x_at:
                inside = not inside
    return inside


def locate_regime(features: list[dict], lat: float, lon: float, default: str = "international") -> str:
    for feat in features:
        geom = feat.get("geometry", {})
        if geom.get("type") != "Polygon":
            continue
        rings = geom.get("coordinates", [])
        if rings and _point_in_ring(lon, lat, rings[0]):
            return feat.get("regime") or default
    return default
