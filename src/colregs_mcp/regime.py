"""Resolve which collision-regs regime applies at a position via point-in-polygon.

Boundary convention is **inclusive**: a point on a polygon edge or vertex belongs
to that regime. Holes (inner rings) and MultiPolygon parts are honored — a point
inside a hole is outside the feature.
"""

from __future__ import annotations

_EPS = 1e-12


def _point_on_ring(lon: float, lat: float, ring: list) -> bool:
    """True when the point lies on a vertex or edge of the ring."""
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        cross = (x2 - x1) * (lat - y1) - (y2 - y1) * (lon - x1)
        if abs(cross) > _EPS:
            continue
        if min(x1, x2) - _EPS <= lon <= max(x1, x2) + _EPS \
                and min(y1, y2) - _EPS <= lat <= max(y1, y2) + _EPS:
            return True
    return False


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


def _point_in_polygon(lon: float, lat: float, rings: list) -> bool:
    """rings[0] is the outer boundary, rings[1:] are holes."""
    if not rings:
        return False
    if _point_on_ring(lon, lat, rings[0]):
        return True
    if not _point_in_ring(lon, lat, rings[0]):
        return False
    for hole in rings[1:]:
        if _point_on_ring(lon, lat, hole):
            return True          # the hole's edge still belongs to the feature
        if _point_in_ring(lon, lat, hole):
            return False
    return True


def locate_regime(features: list[dict], lat: float, lon: float, default: str = "international") -> str:
    for feat in features:
        geom = feat.get("geometry", {})
        gtype = geom.get("type")
        if gtype == "Polygon":
            polygons = [geom.get("coordinates", [])]
        elif gtype == "MultiPolygon":
            polygons = geom.get("coordinates", [])
        else:
            continue
        for rings in polygons:
            if _point_in_polygon(lon, lat, rings):
                return feat.get("regime") or default
    return default
