import geopandas as gpd
from pathlib import Path

gpkg_path = Path(__file__).resolve().parent.parent / "database" / "mongolia_desert_db.gpkg"

print("Өгөгдлийг уншиж байна...")
degraded_gdf = gpd.read_file(gpkg_path, layer="desert_areas_ranked")
aimags_gdf = gpd.read_file(gpkg_path, layer="mongolia_aimags")

# CRS ижилсүүлэх
if degraded_gdf.crs != aimags_gdf.crs:
    aimags_gdf = aimags_gdf.to_crs(degraded_gdf.crs)

print("Орон зайн нэгдэл (Spatial Join) хийж байна...")
joined_gdf = gpd.sjoin(degraded_gdf, aimags_gdf, how="left", predicate="intersects")

# Аймгийн нэр болон талбайн баганыг стандартын дагуу тодорхойлох
if 'name' in joined_gdf.columns and 'aimag_name' not in joined_gdf.columns:
    joined_gdf['aimag_name'] = joined_gdf['name']

if 'area_SqKm' not in joined_gdf.columns and 'area_sqkm' in joined_gdf.columns:
    joined_gdf['area_SqKm'] = joined_gdf['area_sqkm']

# Багануудын нэр давхардаж алдаа гаргахаас сэргийлж зөвхөн шаардлагатай багануудыг үлдээх
cols_to_keep = ['geometry', 'area_SqKm', 'DN', 'aimag_name']
cols_to_keep = [c for c in cols_to_keep if c in joined_gdf.columns]
clean_joined_gdf = joined_gdf[cols_to_keep].copy()

# Өмнөх layer-ийг устгах
import pyogrio
try:
    pyogrio.remove_layer(gpkg_path, "degraded_with_aimags")
except Exception:
    pass

# Шинэ цэвэрлэсэн датагаа GeoPackage рүү хадгалах
clean_joined_gdf.to_file(gpkg_path, layer="degraded_with_aimags", driver="GPKG")
print("-> 'degraded_with_aimags' шинэ давхарга амжилттай хадгалагдлаа!\n")

# Аймаг тус бүрийн талбайн нийт дүн
province_summary = clean_joined_gdf.groupby('aimag_name')['area_SqKm'].sum().reset_index()
province_summary = province_summary.sort_values(by='area_SqKm', ascending=False)

print("=" * 50)
print(" АЙМАГ ТУС БҮРЭЭРХ ЦӨЛЖСӨН ТАЛБАЙН НИЙТ ДҮН (км²)")
print("=" * 50)
print(province_summary.to_string(index=False))
print("-" * 50)

# Улсын хэмжээний нийт дүн
total_mongolia_desert = clean_joined_gdf['area_SqKm'].sum()
print(f"\n МОНГОЛ УЛСЫН ХЭМЖЭЭНД НИЙТ ЦӨЛЖСӨН ТАЛБАЙ: {total_mongolia_desert:,.2f} км²\n")
