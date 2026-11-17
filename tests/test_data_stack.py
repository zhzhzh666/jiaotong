"""Small interoperability checks; these are artificial fixtures, not Shenzhen data."""
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Point


def test_projected_geometry_geojson_and_parquet_roundtrip(tmp_path):
    points = gpd.GeoDataFrame({"fixture_id": [1, 2]}, geometry=[Point(114.0, 22.5), Point(114.001, 22.5)], crs="EPSG:4326")
    projected = points.to_crs("EPSG:32650")
    distance_m = projected.geometry.iloc[0].distance(projected.geometry.iloc[1])
    assert 90 < distance_m < 110
    target = tmp_path / "synthetic_fixture.geojson"
    points.to_file(target, driver="GeoJSON")
    loaded = gpd.read_file(target)
    assert len(loaded) == 2 and loaded.crs.to_epsg() == 4326
    table = pd.DataFrame({"fixture_id": [1, 2], "distance_m": [0.0, distance_m]})
    table.to_parquet(tmp_path / "synthetic_fixture.parquet", index=False)
    pd.testing.assert_frame_equal(table, pd.read_parquet(tmp_path / "synthetic_fixture.parquet"))


def test_geotiff_roundtrip(tmp_path):
    values = np.array([[1, 2], [3, 4]], dtype="float32")
    path = tmp_path / "synthetic_fixture.tif"
    with rasterio.open(path, "w", driver="GTiff", height=2, width=2, count=1, dtype="float32",
                       crs="EPSG:32650", transform=from_origin(200000, 2500000, 10, 10)) as dataset:
        dataset.write(values, 1)
    with rasterio.open(path) as dataset:
        assert dataset.crs.to_epsg() == 32650 and dataset.res == (10, 10)
        np.testing.assert_array_equal(dataset.read(1), values)
