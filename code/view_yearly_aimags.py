import pandas as pd
from pathlib import Path

# CSV файлаас өгөгдлийг унших
database_dir = Path(__file__).resolve().parent.parent / "database"
df = pd.read_csv(database_dir / "mongolia_desert_monthly_aimags.csv")

# Жил болон аймаг тус бүрээр нь нэгтгэх (Жилийн дундаж эсвэл нийлбэр)
yearly_df = df.groupby(['aimag_name', 'year'])['desert_area_sqkm'].mean().reset_index()

# Хүснэгтийг бүрэн дэлгэрэнгүй харуулах
pd.set_option('display.max_rows', None)
pd.set_option('display.width', 1000)

print("=" * 60)
print(" БҮХ АЙМАГ БОЛОН ЖИЛҮҮДИЙН ЦӨЛЖИЛТИЙН СТАТИСТИК")
print("=" * 60)
print(yearly_df)
print("=" * 60)

# Хүсвэл үүнийг шинэ Excel эсвэл CSV файл болгон хадгалж болно
yearly_df.to_excel(database_dir / "Mongolia_Yearly_Aimag_Desertification.xlsx", index=False)
print("Үр дүнг 'Mongolia_Yearly_Aimag_Desertification.xlsx' файл руу амжилттай хадгаллаа!")
