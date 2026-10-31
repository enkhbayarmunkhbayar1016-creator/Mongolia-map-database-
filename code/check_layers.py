import geopandas as gpd
from pathlib import Path

gpkg_path = Path(__file__).resolve().parent.parent / "database" / "mongolia_desert_db.gpkg"
# GeoPandas ашиглан layer-үүдийг жагсаах
import pyogrio
layers = pyogrio.list_layers(gpkg_path)
print("Өгөгдлийн сан доторх layer-үүдийн жагсаалт:")
for l in layers:
    print(f" - {l}")
