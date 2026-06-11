from pathlib import Path
from colregs_mcp.regime import locate_regime
from colregs_mcp.vault import Vault

FIXTURE = Path(__file__).parent / "fixtures" / "vault"

def _features():
    return Vault.load(FIXTURE).regime_features

def test_point_in_canadian_box():
    assert locate_regime(_features(), lat=48.89, lon=-123.39, default="international") == "canadian"

def test_point_outside_falls_back_to_default():
    assert locate_regime(_features(), lat=10.0, lon=-140.0, default="international") == "international"

def test_multipolygon_parts_and_holes():
    # coordinates are [lon, lat]; part 1 is a 2x2 square with a 1x1 hole, part 2 a far square
    features = [{
        "regime": "inland",
        "geometry": {"type": "MultiPolygon", "coordinates": [
            [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]],
             [[0.5, 0.5], [1.5, 0.5], [1.5, 1.5], [0.5, 1.5], [0.5, 0.5]]],
            [[[10, 10], [12, 10], [12, 12], [10, 12], [10, 10]]],
        ]},
    }]
    assert locate_regime(features, lat=11.0, lon=11.0) == "inland"        # second part
    assert locate_regime(features, lat=1.0, lon=1.0) == "international"   # inside the hole
    assert locate_regime(features, lat=0.25, lon=0.25) == "inland"        # between outer ring and hole

def test_polygon_hole_excludes_point():
    features = [{
        "regime": "canadian",
        "geometry": {"type": "Polygon", "coordinates": [
            [[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]],
            [[0.5, 0.5], [1.5, 0.5], [1.5, 1.5], [0.5, 1.5], [0.5, 0.5]],
        ]},
    }]
    assert locate_regime(features, lat=1.0, lon=1.0) == "international"
    assert locate_regime(features, lat=0.25, lon=1.0) == "canadian"

def test_boundary_points_count_as_inside():
    # A demarcation line belongs to the regime it bounds: inclusive convention.
    features = [{
        "regime": "canadian",
        "geometry": {"type": "Polygon",
                     "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]},
    }]
    assert locate_regime(features, lat=0.0, lon=0.0) == "canadian"   # vertex
    assert locate_regime(features, lat=0.0, lon=1.0) == "canadian"   # edge midpoint
    assert locate_regime(features, lat=1.0, lon=2.0) == "canadian"   # vertical edge
