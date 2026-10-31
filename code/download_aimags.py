import geopandas as gpd
from pathlib import Path

print("Монголын аймгийн хилийн өгөгдлийг татаж байна...")
# Natural Earth эсвэл GitHub дээрх нээлттэй Монголын аймгийн хилийн өгөгдлийг ашиглах
# (Энд олон улсын нийтлэг эх сурвалж эсвэл Natural Earth-ийн admin 1 түвшний өгөгдлийг татаж авна)
url = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_1_states_provinces.geojson"

# Бүх дэлхийн мууж/аймгийн өгөгдлийг татаж аваад Монголоор нь шүүж авах
world_provinces = gpd.read_file(url)
mongolia_aimags = world_provinces[world_provinces['admin'] == 'Mongolia']

# Хэрэв аймгийн нэр хадгалагдсан багана өөр байвал шалгаад 'aimag_name' болгож нэрлэх
if 'name' in mongolia_aimags.columns:
    mongolia_aimags['aimag_name'] = mongolia_aimags['name']

# Өөрийн GeoPackage өгөгдлийн сан рүү хадгалах
gpkg_path = Path(__file__).resolve().parent.parent / "database" / "mongolia_desert_db.gpkg"
mongolia_aimags.to_file(gpkg_path, layer="mongolia_aimags", driver="GPKG")

print("Амжилттай! 'mongolia_aimags' давхарга өгөгдлийн санд нэмэгдлээ.")
