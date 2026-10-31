import geopandas as gpd
from pathlib import Path

# 1. GeoPackage өгөгдлийн сантай холбогдох
gpkg_path = Path(__file__).resolve().parent.parent / "database" / "mongolia_desert_db.gpkg"

# 2. Бааз дээрх цөлжсөн бүсийн давхаргыг унших
gdf = gpd.read_file(gpkg_path, layer="mongolia_degraded_areas")

# 3. Эрэмбэлэлт хийх (Талбайн хэмжээгээр буурахаар - зөв бичигдсэн area_SqKm баганаар)
ranked_gdf = gdf.sort_values(by="area_SqKm", ascending=False)

# 4. Хамгийн том 10 бүсийг хэвлэх
print("Хамгийн том 10 цөлжсөн бүс:")
print(ranked_gdf[["DN", "area_SqKm", "geometry"]].head(10))

# 5. Шинэ эрэмбэлэгдсэн хүснэгт болгон GeoPackage дотроо буцааж хадгалах
ranked_gdf.to_file(gpkg_path, layer="desert_areas_ranked", driver="GPKG")

print("\nАмжилттай холбогдож, шинэ эрэмбэлсэн хүснэгтийг баазад үүсгэлээ!")
