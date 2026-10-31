import geopandas as gpd
from pathlib import Path

gpkg_path = Path(__file__).resolve().parent.parent / "database" / "mongolia_desert_db.gpkg"
# Layers жагсаалтыг харах эсвэл шууд унших
gdf = gpd.read_file(gpkg_path, layer="mongolia_degraded_areas")

print("Багануудын нэрс:")
print(gdf.columns)
print("\nЭхний 5 мөр:")
print(gdf.head())
