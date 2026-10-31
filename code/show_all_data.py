import pandas as pd
from pathlib import Path

# CSV файлаас өгөгдлийг унших
csv_path = Path(__file__).resolve().parent.parent / "database" / "mongolia_desert_monthly_aimags.csv"
df = pd.read_csv(csv_path)

# Хүснэгтийг бүрэн дэлгэрэнгүй харуулах тохиргоо (мөр болон баганыг хумихгүй байх)
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

print("=" * 70)
print(" БҮХ АЙМАГ, ЖИЛ, САРЫН ЦӨЛЖИЛТИЙН НАРИЙВЧИЛСЭН ТҮҮХЭН ӨГӨГДӨЛ")
print("=" * 70)
print(df)
print("=" * 70)
print(f"Нийт бичлэгийн тоо: {len(df)} мөр өгөгдөл амжилттай харагдаж байна.")
