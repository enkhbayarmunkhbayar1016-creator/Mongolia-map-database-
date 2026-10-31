from pathlib import Path

import geopandas as gpd
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATABASE_DIR = PROJECT_DIR / "database"
CSV_PATH = DATABASE_DIR / "mongolia_desert_monthly_aimags.csv"
GPKG_PATH = DATABASE_DIR / "mongolia_desert_db.gpkg"

app = FastAPI(title="Монголын Цөлжилтийн Атлас")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if CSV_PATH.exists():
    df = pd.read_csv(CSV_PATH)
else:
    df = pd.DataFrame(columns=["aimag_name", "year", "month", "desert_area_sqkm"])


def _get_gpkg_layers():
    if not GPKG_PATH.exists():
        return []
    try:
        layers = gpd.list_layers(GPKG_PATH)
        if isinstance(layers, pd.DataFrame):
            return layers["name"].dropna().astype(str).tolist()
        return [str(layer) for layer in layers]
    except Exception:
        return []


@app.get("/api/summary")
def api_summary():
    if df.empty:
        return {"aimag_count": 0, "record_count": 0, "year_start": None, "year_end": None, "total_area": 0.0}
    return {
        "aimag_count": int(df["aimag_name"].nunique()),
        "record_count": int(len(df)),
        "year_start": int(df["year"].min()),
        "year_end": int(df["year"].max()),
        "total_area": round(float(df["desert_area_sqkm"].sum()), 2),
    }


@app.get("/api/aimags")
def get_aimags():
    if df.empty:
        return {"aimags": []}
    return {"aimags": sorted(df["aimag_name"].dropna().astype(str).unique().tolist())}


@app.get("/api/years")
def get_years():
    if df.empty:
        return {"years": []}
    return {"years": sorted(df["year"].dropna().astype(int).unique().tolist())}


def _filter_aimags(data: pd.DataFrame, aimag: str | None, aimags: str | None) -> pd.DataFrame:
    if aimags and aimags.strip():
        names = [name.strip().casefold() for name in aimags.split(",") if name.strip()]
        return data[data["aimag_name"].str.casefold().isin(names)]
    if aimag and aimag.strip().casefold() not in {"all", ""}:
        return data[data["aimag_name"].str.casefold() == aimag.strip().casefold()]
    return data


@app.get("/api/desert-data")
def get_desert_data(aimag: str | None = None, aimags: str | None = None, year: str | None = None, month: str | None = None, start_year: int | None = None, end_year: int | None = None):
    if df.empty:
        return []
    res = _filter_aimags(df, aimag, aimags)
    if year is not None and str(year).strip().lower() not in {"all", ""}:
        try:
            res = res[res["year"] == int(year)]
        except ValueError:
            pass
    if month is not None and str(month).strip().lower() not in {"all", ""}:
        try:
            res = res[res["month"] == int(month)]
        except ValueError:
            pass
    if start_year is not None:
        res = res[res["year"] >= start_year]
    if end_year is not None:
        res = res[res["year"] <= end_year]
    return res.to_dict(orient="records")


@app.get("/api/series")
def get_series(aimag: str | None = None, aimags: str | None = None, year: str | None = None, month: str | None = None, start_year: int | None = None, end_year: int | None = None):
    if df.empty:
        return {"labels": [], "values": []}
    res = _filter_aimags(df, aimag, aimags)
    if year is not None and str(year).strip().lower() not in {"all", ""}:
        try:
            res = res[res["year"] == int(year)]
        except ValueError:
            pass
    if month is not None and str(month).strip().lower() not in {"all", ""}:
        try:
            res = res[res["month"] == int(month)]
        except ValueError:
            pass
    if start_year is not None:
        res = res[res["year"] >= start_year]
    if end_year is not None:
        res = res[res["year"] <= end_year]

    if res.empty:
        return {"labels": [], "values": []}

    if year is not None and str(year).strip().lower() not in {"all", ""}:
        monthly = res.groupby("month", as_index=False)["desert_area_sqkm"].sum().sort_values("month")
        return {
            "labels": [int(value) for value in monthly["month"].tolist()],
            "values": [round(float(value), 2) for value in monthly["desert_area_sqkm"].tolist()],
        }

    yearly = res.groupby("year", as_index=False)["desert_area_sqkm"].sum().sort_values("year")
    return {
        "labels": [int(value) for value in yearly["year"].tolist()],
        "values": [round(float(value), 2) for value in yearly["desert_area_sqkm"].tolist()],
    }


@app.get("/api/geopackage")
def get_geopackage_summary():
    layers = _get_gpkg_layers()
    return {"layers": layers, "count": len(layers), "status": "ok" if layers else "missing"}


@app.get("/api/aimag-map")
def get_aimag_map(year: str | None = None, month: str | None = None, start_year: int | None = None, end_year: int | None = None):
    if not GPKG_PATH.exists():
        return {"features": [], "bounds": None}

    aimags = gpd.read_file(GPKG_PATH, layer="mongolia_aimags")
    aimags = aimags[["name", "geometry"]].copy()
    aimags["geometry"] = aimags.geometry.simplify(0.02, preserve_topology=True)
    min_x, min_y, max_x, max_y = aimags.total_bounds.tolist()

    filtered = df
    if year and year.strip().lower() not in {"all", ""}:
        filtered = filtered[filtered["year"] == int(year)]
    if month and month.strip().lower() not in {"all", ""}:
        filtered = filtered[filtered["month"] == int(month)]
    if start_year is not None:
        filtered = filtered[filtered["year"] >= start_year]
    if end_year is not None:
        filtered = filtered[filtered["year"] <= end_year]
    area_by_aimag = filtered.groupby("aimag_name")["desert_area_sqkm"].mean().to_dict()

    features = []
    for _, row in aimags.iterrows():
        geometry = row.geometry
        label = geometry.representative_point()
        features.append({
            "name": str(row["name"]),
            "geometry": geometry.__geo_interface__,
            "label": [float(label.x), float(label.y)],
            "area_sqkm": round(float(area_by_aimag.get(row["name"], 0)), 2),
        })

    return {
        "features": features,
        "bounds": [float(min_x), float(min_y), float(max_x), float(max_y)],
    }


HTML_PAGE = """
<!DOCTYPE html>
<html lang="mn" class="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Монголын Цөлжилтийн Атлас (2002–2022)</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            desert: {
              50: '#fdfbf7',
              100: '#f7f2e7',
              200: '#ebdcc4',
              300: '#dfc29c',
              400: '#ce9f6b',
              500: '#bf8346',
              600: '#a66839',
              700: '#874f31',
              800: '#6f412d',
              900: '#5c3729',
              950: '#1c1512',
              dark: '#14100e',
              panel: '#1e1815',
              card: '#261f1b',
              border: '#3b2f28'
            },
            accent: {
              amber: '#d97706',
              gold: '#f59e0b',
              sand: '#e5c158',
              danger: '#ef4444',
              teal: '#14b8a6'
            }
          },
          fontFamily: {
            sans: ['Inter', 'sans-serif']
          }
        }
      }
    }
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {
      --bg: #14100e;
      --panel: #1e1815;
      --card: #261f1b;
      --border: #3b2f28;
      --amber: #f59e0b;
      --gold: #d97706;
      --text: #ebdcc4;
      --muted: #a68d7a;
    }

    html { scroll-behavior: smooth; }
    body {
      font-family: 'Inter', sans-serif;
      background: var(--bg);
      color: var(--text);
      overflow-x: hidden;
    }

    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: #1c1512; }
    ::-webkit-scrollbar-thumb { background: #3b2f28; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #bf8346; }

    .glass-panel {
      background: rgba(30, 24, 21, 0.76);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(191, 131, 70, 0.15);
    }
    .glow-amber { box-shadow: 0 0 25px -5px rgba(217, 119, 6, 0.35); }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    .nav-btn.active {
      background: rgba(38, 31, 27, 0.95);
      color: #f7d38d;
      box-shadow: inset 0 0 0 1px rgba(191, 131, 70, 0.2);
    }
    .map-aimag {
      transition: all 0.2s ease;
      cursor: pointer;
      opacity: 0.92;
    }
    .map-aimag:hover { fill: #f59e0b !important; }
    .map-aimag.active { fill: #ef4444 !important; }
    .map-tile {
      background: linear-gradient(135deg, rgba(164,110,69,0.90), rgba(113,72,53,0.95));
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 10px 14px 12px 10px;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.04);
    }
    .aimag-map { width: 100%; height: auto; min-height: 260px; scroll-margin-top: 6rem; }
    .aimag-map-path { stroke: #1c1512; stroke-width: 1.5; cursor: pointer; transition: fill 0.15s ease, stroke 0.15s ease; }
    .aimag-map-path:hover, .aimag-map-path:focus { fill: #f59e0b !important; stroke: #fff; stroke-width: 2.5; outline: none; }
    .aimag-map-path.selected { stroke: #fff; stroke-width: 3; }
    .aimag-map-label { fill: #fff8eb; font-size: 11px; font-weight: 600; text-anchor: middle; paint-order: stroke; stroke: #1c1512; stroke-width: 2.5px; stroke-linejoin: round; pointer-events: none; }
  </style>
</head>
<body class="min-h-screen flex flex-col justify-between selection:bg-desert-600 selection:text-white">
  <header class="sticky top-0 z-50 glass-panel border-b border-desert-border/50 px-4 lg:px-8 py-3 transition-all duration-300">
    <div class="max-w-7xl mx-auto flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-desert-500 to-accent-amber flex items-center justify-center text-desert-950 font-bold text-xl shadow-lg glow-amber">Г</div>
        <div>
          <span class="text-[10px] uppercase tracking-[0.28rem] text-desert-400 font-semibold block">Монгол улс</span>
          <h1 class="text-sm md:text-base font-bold text-desert-100 tracking-tight leading-none">Монголын Газрын Мэдээллийн Сангийн Төв</h1>
        </div>
      </div>

      <nav class="hidden md:flex items-center space-x-1 lg:space-x-2 bg-desert-950/60 p-1.5 rounded-xl border border-desert-border/40">
        <button data-tab="home" class="nav-btn active px-4 py-2 rounded-lg text-sm font-medium transition-all text-accent-gold"> <i class="fa-solid fa-house mr-2 text-xs"></i>Нүүр</button>
        <button data-tab="atlas" class="nav-btn px-4 py-2 rounded-lg text-sm font-medium transition-all text-desert-300 hover:text-desert-100 hover:bg-desert-card/50"> <i class="fa-solid fa-map-location-dot mr-2 text-xs"></i>Атлас</button>
        <button data-tab="compare" class="nav-btn px-4 py-2 rounded-lg text-sm font-medium transition-all text-desert-300 hover:text-desert-100 hover:bg-desert-card/50"> <i class="fa-solid fa-code-compare mr-2 text-xs"></i>Харьцуулах</button>
        <button data-tab="database" class="nav-btn px-4 py-2 rounded-lg text-sm font-medium transition-all text-desert-300 hover:text-desert-100 hover:bg-desert-card/50"> <i class="fa-solid fa-database mr-2 text-xs"></i>Мэдээллийн сан</button>
        <button data-tab="methodology" class="nav-btn px-4 py-2 rounded-lg text-sm font-medium transition-all text-desert-300 hover:text-desert-100 hover:bg-desert-card/50"> <i class="fa-solid fa-book-bookmark mr-2 text-xs"></i>Арга зүй</button>
      </nav>

      <div class="flex items-center space-x-3">
        <div class="hidden sm:flex items-center bg-desert-card px-3 py-1.5 rounded-lg border border-desert-border text-xs text-desert-300">
          <span class="w-2 h-2 rounded-full bg-emerald-500 mr-2 animate-pulse"></span>
          2002–2022 СУДАЛГАА
        </div>
        <button id="mobile-menu-btn" class="md:hidden text-desert-200 hover:text-white p-2 text-lg">
          <i class="fa-solid fa-bars"></i>
        </button>
      </div>
    </div>

    <div id="mobile-menu" class="hidden md:hidden mt-3 pt-3 border-t border-desert-border flex flex-col space-y-2">
      <button data-tab="home" class="nav-btn active text-left px-4 py-2 rounded-lg text-sm text-desert-100 hover:bg-desert-card">Нүүр</button>
      <button data-tab="atlas" class="nav-btn text-left px-4 py-2 rounded-lg text-sm text-desert-100 hover:bg-desert-card">Атлас үзэх</button>
      <button data-tab="compare" class="nav-btn text-left px-4 py-2 rounded-lg text-sm text-desert-100 hover:bg-desert-card">Харьцуулах</button>
      <button data-tab="database" class="nav-btn text-left px-4 py-2 rounded-lg text-sm text-desert-100 hover:bg-desert-card">Мэдээллийн сан</button>
      <button data-tab="methodology" class="nav-btn text-left px-4 py-2 rounded-lg text-sm text-desert-100 hover:bg-desert-card">Арга зүй</button>
    </div>
  </header>

  <main class="flex-grow max-w-7xl w-full mx-auto px-4 lg:px-8 py-6">
    <section id="home" class="tab-content active space-y-10">
      <div class="relative rounded-3xl overflow-hidden border border-desert-border bg-gradient-to-r from-desert-950 via-desert-panel to-desert-card p-8 md:p-12">
        <div class="absolute inset-0 opacity-10 bg-[radial-gradient(#d97706_1px,transparent_1px)] [background-size:16px_16px]"></div>
        <div class="relative z-10 max-w-2xl space-y-4">
          <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-desert-500/20 text-accent-gold border border-desert-500/30">
            <i class="fa-solid fa-earth-asia mr-1.5"></i> Орон зайн ГИС Атлас
          </span>
          <h1 class="text-3xl md:text-5xl font-extrabold text-desert-100 tracking-tight leading-tight">
            Өөрчлөгдөж буй газар нутаг.<br>
            <span class="text-transparent bg-clip-text bg-gradient-to-r from-accent-gold via-desert-400 to-accent-amber">Урт хугацааны чиг хандлага.</span>
          </h1>
          <p class="text-desert-300 text-sm md:text-base leading-relaxed">
            Монгол Улсын 22 аймгийн цөлжилтийн түүхэн мэдээллийг 2002–2022 оны хооронд нарийвчлан харах, статистик харьцуулалт хийх болон вектор өгөгдлийн санг ашиглах орон зайн Атлас.
          </p>
          <div class="flex flex-wrap gap-4 pt-2">
            <button data-tab="atlas" class="tab-btn px-6 py-3 rounded-xl bg-gradient-to-r from-desert-500 to-accent-amber text-desert-950 font-semibold text-sm hover:brightness-110 transition shadow-lg glow-amber flex items-center">
              Атлас үзэх <i class="fa-solid fa-arrow-right-long ml-2"></i>
            </button>
            <button data-tab="database" class="tab-btn px-6 py-3 rounded-xl bg-desert-card border border-desert-border text-desert-200 font-medium text-sm hover:bg-desert-border transition flex items-center">
              Мэдээллийн сан <i class="fa-solid fa-table-list ml-2 text-desert-400"></i>
            </button>
          </div>
        </div>
        <div class="mt-8 md:mt-0 md:absolute md:right-8 md:bottom-8 grid grid-cols-3 gap-4 text-center">
          <div class="bg-desert-950/80 p-4 rounded-2xl border border-desert-border/60">
            <div id="home-aimags" class="text-2xl font-bold text-accent-gold">22</div>
            <div class="text-xs text-desert-400">Аймаг</div>
          </div>
          <div class="bg-desert-950/80 p-4 rounded-2xl border border-desert-border/60">
            <div id="home-records" class="text-2xl font-bold text-accent-gold">0</div>
            <div class="text-xs text-desert-400">Бүртгэл</div>
          </div>
          <div class="bg-desert-950/80 p-4 rounded-2xl border border-desert-border/60">
            <div id="home-years" class="text-2xl font-bold text-accent-gold">21</div>
            <div class="text-xs text-desert-400">Жилийн динамик</div>
          </div>
        </div>
      </div>

      <div>
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-xl font-bold text-desert-100 flex items-center"><i class="fa-solid fa-layer-group text-accent-gold mr-2.5"></i> Бүсчилсэн Шинжилгээ</h2>
          <span class="text-xs text-desert-400">Бүс нутгийн ангилал</span>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div class="bg-desert-panel rounded-2xl p-6 border border-desert-border hover:border-desert-500/50 transition group">
            <div class="flex items-center justify-between mb-3">
              <span class="text-xs font-bold text-accent-amber uppercase tracking-wider">Өмнөд Бүс</span>
              <i class="fa-solid fa-sun text-desert-500 group-hover:scale-110 transition"></i>
            </div>
            <h3 class="text-lg font-bold text-desert-100 mb-2">Говь ба тал хээр</h3>
            <p class="text-xs text-desert-300 leading-relaxed mb-4">Өмнөговь, Дорноговь, Дундговь аймгуудын цөлжилтийн индекс болон дулаарлын нөлөөллийн урт хугацааны хэлбэлзэл.</p>
            <button data-region-name="Өмнөд Бүс" data-aimags="Ömnögovi,Dornogovi,Dundgovi" class="region-btn text-xs font-semibold text-accent-gold hover:underline flex items-center">
              Бүсээр шүүх <i class="fa-solid fa-chevron-right ml-1 text-[10px]"></i>
            </button>
          </div>

          <div class="bg-desert-panel rounded-2xl p-6 border border-desert-border hover:border-desert-500/50 transition group">
            <div class="flex items-center justify-between mb-3">
              <span class="text-xs font-bold text-accent-amber uppercase tracking-wider">Баруун Бүс</span>
              <i class="fa-solid fa-mountain text-desert-500 group-hover:scale-110 transition"></i>
            </div>
            <h3 class="text-lg font-bold text-desert-100 mb-2">Алтай ба уулархаг нутаг</h3>
            <p class="text-xs text-desert-300 leading-relaxed mb-4">Ховд, Говь-Алтай, Баян-Өлгий аймгуудын бэлчээрийн талхагдал болон хөрсний чийгшлийн бууралтын судалгаа.</p>
            <button data-region-name="Баруун Бүс" data-aimags="Hovd,Govi-Altay,Bayan-Ölgiy" class="region-btn text-xs font-semibold text-accent-gold hover:underline flex items-center">
              Бүсээр шүүх <i class="fa-solid fa-chevron-right ml-1 text-[10px]"></i>
            </button>
          </div>

          <div class="bg-desert-panel rounded-2xl p-6 border border-desert-border hover:border-desert-500/50 transition group">
            <div class="flex items-center justify-between mb-3">
              <span class="text-xs font-bold text-accent-amber uppercase tracking-wider">Зүүн Бүс</span>
              <i class="fa-solid fa-wind text-desert-500 group-hover:scale-110 transition"></i>
            </div>
            <h3 class="text-lg font-bold text-desert-100 mb-2">Тал хээрийн бүс нутаг</h3>
            <p class="text-xs text-desert-300 leading-relaxed mb-4">Дорнод, Сүхбаатар, Хэнтий аймгуудын хээрийн бүсийн эмзэг байдал ба цөлжилтийн тэлэлт.</p>
            <button data-region-name="Зүүн Бүс" data-aimags="Dornod,Sühbaatar,Hentiy" class="region-btn text-xs font-semibold text-accent-gold hover:underline flex items-center">
              Бүсээр шүүх <i class="fa-solid fa-chevron-right ml-1 text-[10px]"></i>
            </button>
          </div>
        </div>
      </div>
    </section>

    <section id="atlas" class="tab-content space-y-6">
      <div class="bg-desert-panel p-4 rounded-2xl border border-desert-border flex flex-wrap items-center justify-between gap-4">
        <div class="flex flex-wrap items-center gap-3 w-full lg:w-auto">
          <div class="flex flex-col">
            <label class="text-[10px] text-desert-400 font-semibold mb-1 uppercase tracking-wider">Аймаг сонгох</label>
            <select id="filter-aimag" class="bg-desert-card border border-desert-border text-desert-100 text-xs rounded-xl px-3 py-2 outline-none focus:border-accent-gold transition min-w-[170px]">
              <option value="ALL">Бүх 22 аймаг</option>
            </select>
          </div>
          <div class="flex flex-col">
            <label class="text-[10px] text-desert-400 font-semibold mb-1 uppercase tracking-wider">Он</label>
            <select id="filter-year" class="bg-desert-card border border-desert-border text-desert-100 text-xs rounded-xl px-3 py-2 outline-none focus:border-accent-gold transition min-w-[120px]">
              <option value="ALL">Бүх он</option>
            </select>
          </div>
          <div class="flex flex-col">
            <label class="text-[10px] text-desert-400 font-semibold mb-1 uppercase tracking-wider">Сар</label>
            <select id="filter-month" class="bg-desert-card border border-desert-border text-desert-100 text-xs rounded-xl px-3 py-2 outline-none focus:border-accent-gold transition min-w-[120px]">
              <option value="ALL">Бүх сар</option>
            </select>
          </div>
          <div class="flex flex-col">
            <label class="text-[10px] text-desert-400 font-semibold mb-1 uppercase tracking-wider">Эхлэх он</label>
            <select id="filter-start-year" class="bg-desert-card border border-desert-border text-desert-100 text-xs rounded-xl px-3 py-2 outline-none focus:border-accent-gold transition"></select>
          </div>
          <div class="flex flex-col">
            <label class="text-[10px] text-desert-400 font-semibold mb-1 uppercase tracking-wider">Дуусгах он</label>
            <select id="filter-end-year" class="bg-desert-card border border-desert-border text-desert-100 text-xs rounded-xl px-3 py-2 outline-none focus:border-accent-gold transition"></select>
          </div>
        </div>
      </div>

      <div class="rounded-2xl border border-desert-border bg-desert-panel p-5">
        <div class="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h2 class="text-base font-bold text-desert-100"><i class="fa-solid fa-map text-accent-gold mr-2"></i> Монгол Улсын Аймгуудын Зураг</h2>
            <p class="text-xs text-desert-300 mt-1">Аймаг дээр дарж Атлас болон Мэдээллийн сангийн өгөгдлийг сонгоно уу.</p>
          </div>
          <div class="flex items-center gap-3">
            <span id="atlas-map-selected" class="text-xs text-accent-gold">Бүх аймаг</span>
            <button type="button" data-map-reset class="text-xs text-desert-300 hover:text-white underline">Сонголт арилгах</button>
          </div>
        </div>
        <div class="rounded-xl border border-desert-border/60 bg-desert-dark/60 p-2 overflow-hidden">
          <svg id="atlas-aimag-map" class="aimag-map" viewBox="0 0 960 500" role="group" aria-label="Монгол Улсын аймгуудын сонголттой зураг"></svg>
        </div>
        <div class="flex flex-wrap gap-x-5 gap-y-2 mt-3 text-[11px] text-desert-300">
          <span><i class="inline-block w-3 h-3 rounded-sm bg-[#6f412d] mr-1 align-middle"></i>Бага (&lt; 1,000 км²)</span>
          <span><i class="inline-block w-3 h-3 rounded-sm bg-[#a66839] mr-1 align-middle"></i>Дунд (1,000–4,000 км²)</span>
          <span><i class="inline-block w-3 h-3 rounded-sm bg-[#d97706] mr-1 align-middle"></i>Өндөр (4,000–8,000 км²)</span>
          <span><i class="inline-block w-3 h-3 rounded-sm bg-[#ef4444] mr-1 align-middle"></i>Маш өндөр (&gt; 8,000 км²)</span>
        </div>
        <p class="text-[11px] text-desert-400 mt-2">Өнгө нь сонгосон хугацааны сарын дундаж цөлжилтийн талбайг харуулна.</p>
      </div>

      <div class="grid grid-cols-1 xl:grid-cols-[1.7fr_0.9fr] gap-6">
        <div class="rounded-2xl border border-desert-border bg-desert-panel p-5">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-desert-100">Жилийн цөлжилтийн динамик</h2>
            <span id="atlas-selected" class="text-xs uppercase tracking-[0.14em] text-desert-400">Бүх аймаг</span>
          </div>
          <div class="h-[340px]">
            <canvas id="atlas-chart"></canvas>
          </div>
        </div>

        <div class="space-y-6">
          <div class="rounded-2xl border border-desert-border bg-desert-panel p-5">
            <h3 class="text-base font-semibold text-desert-100 mb-4">Үндсэн үзүүлэлт</h3>
            <div class="space-y-4 text-sm text-desert-300">
              <div class="flex justify-between border-b border-desert-border pb-2"><span>Хамгийн их</span><span id="peak-value" class="font-semibold text-accent-gold">—</span></div>
              <div class="flex justify-between border-b border-desert-border pb-2"><span>Талбай</span><span id="peak-area" class="font-semibold text-accent-gold">—</span></div>
              <div class="flex justify-between border-b border-desert-border pb-2"><span>Сүүлчийн жил</span><span id="latest-year" class="font-semibold text-desert-100">—</span></div>
              <div class="flex justify-between"><span>Дундаж</span><span id="avg-area" class="font-semibold text-accent-gold">—</span></div>
            </div>
          </div>

          <div class="rounded-2xl border border-desert-border bg-desert-panel p-5">
            <h3 class="text-base font-semibold text-desert-100 mb-3">Бүсийн жагсаалт</h3>
            <div id="region-list" class="space-y-2 text-sm text-desert-300"></div>
          </div>
        </div>
      </div>
    </section>

    <section id="compare" class="tab-content">
      <div class="rounded-2xl border border-desert-border bg-desert-panel p-5">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-5">
          <label class="flex flex-col text-[10px] text-desert-400 font-semibold uppercase tracking-wider">
            1-р аймаг
            <select id="compare-a" class="mt-2 bg-desert-card border border-desert-border text-desert-100 text-xs rounded-xl px-3 py-2 outline-none focus:border-accent-gold transition"></select>
          </label>
          <label class="flex flex-col text-[10px] text-desert-400 font-semibold uppercase tracking-wider">
            2-р аймаг
            <select id="compare-b" class="mt-2 bg-desert-card border border-desert-border text-desert-100 text-xs rounded-xl px-3 py-2 outline-none focus:border-accent-gold transition"></select>
          </label>
          <label class="flex flex-col text-[10px] text-desert-400 font-semibold uppercase tracking-wider">
            Эхлэх он
            <select id="compare-start-year" class="mt-2 bg-desert-card border border-desert-border text-desert-100 text-xs rounded-xl px-3 py-2 outline-none focus:border-accent-gold transition"></select>
          </label>
          <label class="flex flex-col text-[10px] text-desert-400 font-semibold uppercase tracking-wider">
            Дуусгах он
            <select id="compare-end-year" class="mt-2 bg-desert-card border border-desert-border text-desert-100 text-xs rounded-xl px-3 py-2 outline-none focus:border-accent-gold transition"></select>
          </label>
        </div>
        <div class="h-[350px]"><canvas id="compare-chart"></canvas></div>
      </div>
    </section>

    <section id="database" class="tab-content space-y-6">
      <div class="rounded-2xl border border-desert-border bg-desert-panel p-5">
        <div class="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h2 class="text-base font-bold text-desert-100"><i class="fa-solid fa-map text-accent-gold mr-2"></i> Монгол Улсын Аймгуудын Зураг</h2>
            <p class="text-xs text-desert-300 mt-1">Аймаг сонгоход доорх хүснэгт тухайн аймгийн мэдээллээр шүүгдэнэ.</p>
          </div>
          <div class="flex items-center gap-3">
            <span id="database-map-selected" class="text-xs text-accent-gold">Бүх аймаг</span>
            <button type="button" data-map-reset class="text-xs text-desert-300 hover:text-white underline">Сонголт арилгах</button>
          </div>
        </div>
        <div class="rounded-xl border border-desert-border/60 bg-desert-dark/60 p-2 overflow-hidden">
          <svg id="database-aimag-map" class="aimag-map" viewBox="0 0 960 500" role="group" aria-label="Мэдээллийн сангийн аймаг сонгох зураг"></svg>
        </div>
        <div class="flex flex-wrap gap-x-5 gap-y-2 mt-3 text-[11px] text-desert-300">
          <span><i class="inline-block w-3 h-3 rounded-sm bg-[#6f412d] mr-1 align-middle"></i>Бага (&lt; 1,000 км²)</span>
          <span><i class="inline-block w-3 h-3 rounded-sm bg-[#a66839] mr-1 align-middle"></i>Дунд (1,000–4,000 км²)</span>
          <span><i class="inline-block w-3 h-3 rounded-sm bg-[#d97706] mr-1 align-middle"></i>Өндөр (4,000–8,000 км²)</span>
          <span><i class="inline-block w-3 h-3 rounded-sm bg-[#ef4444] mr-1 align-middle"></i>Маш өндөр (&gt; 8,000 км²)</span>
        </div>
        <p class="text-[11px] text-desert-400 mt-2">Өнгө нь сонгосон хугацааны сарын дундаж цөлжилтийн талбайг харуулна.</p>
      </div>

      <div class="rounded-2xl border border-desert-border bg-desert-panel p-5 md:p-6 space-y-5">
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 class="text-lg font-bold text-desert-100 flex items-center">
              <i class="fa-solid fa-database text-accent-gold mr-2.5"></i> Мэдээллийн сан
            </h2>
            <p class="text-xs text-desert-300 mt-1">Аймаг бүрийн сар, жилийн цөлжсөн талбайн статистик өгөгдөл</p>
          </div>
          <div class="flex flex-wrap items-center gap-3">
            <label class="flex flex-col gap-1 text-[10px] text-desert-400 font-semibold">
              Аймаг
              <select id="database-filter-aimag" class="bg-desert-card border border-desert-border text-desert-100 text-xs rounded-xl px-3 py-2 outline-none focus:border-accent-gold">
                <option value="ALL">Бүх аймаг</option>
              </select>
            </label>
            <label class="flex flex-col gap-1 text-[10px] text-desert-400 font-semibold">
              Он
              <select id="database-filter-year" class="bg-desert-card border border-desert-border text-desert-100 text-xs rounded-xl px-3 py-2 outline-none focus:border-accent-gold">
                <option value="ALL">Бүх он</option>
              </select>
            </label>
            <label class="flex flex-col gap-1 text-[10px] text-desert-400 font-semibold">
              Сар
              <select id="database-filter-month" class="bg-desert-card border border-desert-border text-desert-100 text-xs rounded-xl px-3 py-2 outline-none focus:border-accent-gold">
                <option value="ALL">Бүх сар</option>
              </select>
            </label>
            <label class="relative min-w-[220px]">
              <span class="sr-only">Өгөгдөл хайх</span>
              <i class="fa-solid fa-magnifying-glass absolute left-3 top-3 text-desert-400 text-xs"></i>
              <input id="table-search" type="search" placeholder="Аймаг, он, сар хайх..."
                class="w-full bg-desert-card border border-desert-border text-desert-100 text-xs rounded-xl pl-9 pr-4 py-2 outline-none focus:border-accent-gold">
            </label>
            <button id="export-csv" type="button" class="px-4 py-2 rounded-xl bg-desert-card border border-desert-border text-accent-gold text-xs hover:bg-desert-border transition flex items-center font-medium">
              <i class="fa-solid fa-file-csv mr-2 text-sm"></i> CSV файлаар татах
            </button>
            <span id="table-count" class="text-xs uppercase tracking-[0.12em] text-desert-400">0 мөр</span>
          </div>
        </div>

        <div class="overflow-x-auto rounded-xl border border-desert-border/60">
          <table class="w-full text-left border-collapse text-xs">
            <thead class="bg-desert-950/90 text-desert-400 uppercase tracking-wider font-semibold border-b border-desert-border">
              <tr>
                <th class="p-3.5"><button type="button" data-sort="aimag_name" class="hover:text-white">Аймаг <i class="fa-solid fa-sort ml-1"></i></button></th>
                <th class="p-3.5"><button type="button" data-sort="year" class="hover:text-white">Он <i class="fa-solid fa-sort ml-1"></i></button></th>
                <th class="p-3.5"><button type="button" data-sort="month" class="hover:text-white">Сар <i class="fa-solid fa-sort ml-1"></i></button></th>
                <th class="p-3.5"><button type="button" data-sort="desert_area_sqkm" class="hover:text-white">Цөлжсөн талбай (км²) <i class="fa-solid fa-sort ml-1"></i></button></th>
              </tr>
            </thead>
            <tbody id="data-table-body" class="divide-y divide-desert-border/40 text-desert-200"></tbody>
          </table>
        </div>

        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-desert-400">
          <span id="pagination-info" aria-live="polite">Үр дүн: 0-0 / 0</span>
          <div class="flex items-center space-x-2">
            <button id="btn-prev-page" type="button" class="px-3 py-1.5 rounded-lg bg-desert-card border border-desert-border disabled:opacity-40 disabled:cursor-not-allowed">
              <i class="fa-solid fa-chevron-left mr-1"></i> Өмнөх
            </button>
            <span id="page-number-display" class="font-semibold text-desert-200 px-2">1 / 1</span>
            <button id="btn-next-page" type="button" class="px-3 py-1.5 rounded-lg bg-desert-card border border-desert-border disabled:opacity-40 disabled:cursor-not-allowed">
              Дараах <i class="fa-solid fa-chevron-right ml-1"></i>
            </button>
          </div>
        </div>
      </div>

      <div class="rounded-2xl border border-desert-border bg-desert-panel p-5 md:p-6">
        <div class="flex items-center justify-between gap-3 mb-4">
          <div>
            <h3 class="text-base font-bold text-desert-100 flex items-center"><i class="fa-solid fa-layer-group text-accent-gold mr-2.5"></i> Орон зайн мэдээллийн сан</h3>
            <p class="text-xs text-desert-300 mt-1">GeoPackage файлд хадгалагдсан ГИС давхаргууд</p>
          </div>
          <span id="geopackage-status" class="text-xs text-desert-400">Уншиж байна...</span>
        </div>
        <ul id="geopackage-layers" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs text-desert-200" aria-live="polite"></ul>
      </div>
    </section>

    <section id="methodology" class="tab-content">
      <div class="bg-desert-panel rounded-2xl border border-desert-border p-6 md:p-8 space-y-6">
        <div>
          <h2 class="text-xl font-bold text-desert-100 flex items-center mb-2"><i class="fa-solid fa-book-bookmark text-accent-gold mr-2.5"></i> Арга Зүй ба Эх Сурвалж</h2>
          <p class="text-sm text-desert-300">Цөлжилтийн орон зайн шинжилгээний математик болон ГИС боловсруулалтын зарчим</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs text-desert-300 leading-relaxed">
          <div class="bg-desert-card p-5 rounded-xl border border-desert-border/60 space-y-3">
            <h3 class="font-bold text-accent-gold text-sm flex items-center"><i class="fa-solid fa-satellite mr-2"></i> Өгөгдөл Боловсруулалт</h3>
            <p>Энэхүү Атласын мэдээллийг 2002-2022 оны хиймэл дагуулын (MODIS, Landsat) ургамалжлын индекс (NDVI) болон хөрсний чийгшлийн урт хугацааны цуваа өгөгдөлд үндэслэн тооцоолсон.</p>
            <p>ГИС орон зайн нэгдэл (`Spatial Join`) хийх замаар Монгол Улсын засаг захиргааны аймгуудын хилийн цэвэр цөлжсөн полигонуудыг квадрат километрээр (`км²`) бодож гаргасан.</p>
          </div>

          <div class="bg-desert-card p-5 rounded-xl border border-desert-border/60 space-y-3">
            <h3 class="font-bold text-accent-gold text-sm flex items-center"><i class="fa-solid fa-calculator mr-2"></i> Тооцооллын Томьёо</h3>
            <p>Аймаг бүрийн сар ба жилийн цөлжилтийн талбайг дараах орон зайн интегралчлалаар боддог:</p>
            <div class="bg-desert-dark p-3 rounded-lg font-mono text-[11px] text-accent-gold border border-desert-border">Area = ∑ (Pixel_Area × Desertification_Rank_Weight)</div>
            <p>Нийт 5,544 бичлэг нь 22 аймаг × 21 жил × 12 сарын огтлолцол дээр нарийвчилсан статистикийг бүрдүүлдэг.</p>
          </div>
        </div>

        <div class="space-y-3">
          <h3 class="text-sm font-bold text-desert-100">Нэр Томьёоны Толь</h3>
          <div class="overflow-x-auto rounded-xl border border-desert-border/50">
            <table class="w-full text-left text-xs border-collapse">
              <thead class="bg-desert-950 text-desert-400">
                <tr>
                  <th class="p-3 border-b border-desert-border">Нэр томьёо</th>
                  <th class="p-3 border-b border-desert-border">Англи нэршил</th>
                  <th class="p-3 border-b border-desert-border">Тайлбар</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-desert-border/30 text-desert-300">
                <tr><td class="p-3 font-semibold text-desert-100">Цөлжилтийн талбай</td><td class="p-3 font-mono text-accent-gold">Desertified Area (sq km)</td><td class="p-3">Хөрс болон ургамалжилтын доройтолд орсон нийт талбайн хэмжээ.</td></tr>
                <tr><td class="p-3 font-semibold text-desert-100">Орон зайн нэгдэл</td><td class="p-3 font-mono text-accent-gold">Spatial Join (sjoin)</td><td class="p-3">ГИС давхаргуудыг солбицлын системээр тохируулан давхардуулах процесс.</td></tr>
                <tr><td class="p-3 font-semibold text-desert-100">Жилийн дундаж</td><td class="p-3 font-mono text-accent-gold">Yearly Mean Aggregation</td><td class="p-3">12 сарын цөлжилтийн утгын дунджийг тухайн жилийн төлөөлөл болгон авах.</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  </main>

  <footer class="glass-panel border-t border-desert-border/60 py-6 px-4 lg:px-8 mt-12">
    <div class="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between text-xs text-desert-400 gap-4">
      <div>
        <p class="font-semibold text-desert-200">МОНГОЛЫН ГАЗРЫН МЭДЭЭЛЛИЙН САНГИЙН ТӨВ &copy; 2002–2022</p>
        <p class="text-[11px] mt-0.5">Цөлжилтийн орон зайн шинжилгээний веб портал</p>
      </div>
      <div class="flex items-center space-x-6">
        <button data-tab="home" class="tab-btn hover:text-accent-gold transition">Нүүр</button>
        <button data-tab="atlas" class="tab-btn hover:text-accent-gold transition">Атлас</button>
        <button data-tab="database" class="tab-btn hover:text-accent-gold transition">Мэдээллийн сан</button>
        <a href="#top" class="text-desert-300 hover:text-white"><i class="fa-solid fa-arrow-up mr-1"></i> Дээшээ</a>
      </div>
    </div>
  </footer>

  <script>
    const state = { aimag: 'ALL', aimags: [], regionName: '', year: 'ALL', month: 'ALL', startYear: 2002, endYear: 2022 };
    let atlasChart = null;
    let compareChart = null;
    let databaseRows = [];
    let filteredDatabaseRows = [];
    let databasePage = 1;
    let databaseSort = { column: 'aimag_name', ascending: true };
    const databasePageSize = 25;
    let aimagMapFeatures = [];
    let aimagMapBounds = null;

    const allTabs = ['home', 'atlas', 'compare', 'database', 'methodology'];

    function setActiveTab(tab) {
      allTabs.forEach(name => {
        document.getElementById(name)?.classList.toggle('active', name === tab);
      });
      document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
      });
      document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
      });
    }

    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => setActiveTab(btn.dataset.tab));
    });

    document.getElementById('mobile-menu-btn')?.addEventListener('click', () => {
      const menu = document.getElementById('mobile-menu');
      if (menu) menu.classList.toggle('hidden');
    });

    document.querySelectorAll('.nav-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        setActiveTab(btn.dataset.tab);
        const menu = document.getElementById('mobile-menu');
        if (menu) menu.classList.add('hidden');
      });
    });

    document.getElementById('table-search').addEventListener('input', () => {
      databasePage = 1;
      applyDatabaseFilters();
    });
    document.querySelectorAll('[data-sort]').forEach(button => {
      button.addEventListener('click', () => sortDatabaseTable(button.dataset.sort));
    });
    document.getElementById('btn-prev-page').addEventListener('click', () => changeDatabasePage(-1));
    document.getElementById('btn-next-page').addEventListener('click', () => changeDatabasePage(1));
    document.getElementById('export-csv').addEventListener('click', exportDatabaseCsv);
    document.querySelectorAll('.aimag-map').forEach(map => {
      map.addEventListener('click', event => {
        const path = event.target.closest('[data-aimag]');
        if (path) selectAimag(path.dataset.aimag);
      });
      map.addEventListener('keydown', event => {
        const path = event.target.closest('[data-aimag]');
        if (path && (event.key === 'Enter' || event.key === ' ')) {
          event.preventDefault();
          selectAimag(path.dataset.aimag);
        }
      });
    });
    document.querySelectorAll('[data-map-reset]').forEach(button => {
      button.addEventListener('click', () => selectAimag('ALL'));
    });

    document.querySelectorAll('.region-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const names = (btn.dataset.aimags || '').split(',').map(name => name.trim()).filter(Boolean);
        const available = new Set(Array.from(document.getElementById('filter-aimag').options, option => option.value));
        if (names.length && names.every(name => available.has(name))) {
          selectRegion(names, btn.dataset.regionName || 'Бүс');
          setActiveTab('atlas');
        } else {
          console.error('Regional analysis contains an unknown aimag:', names);
        }
      });
    });

    function populateSelect(selectEl, values, placeholder = null) {
      selectEl.innerHTML = '';
      if (placeholder) {
        const option = document.createElement('option');
        option.value = placeholder.value;
        option.textContent = placeholder.label;
        selectEl.appendChild(option);
      }
      values.forEach(value => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = value;
        selectEl.appendChild(option);
      });
    }

    async function fetchJson(url) {
      const r = await fetch(url);
      if (!r.ok) throw new Error('Request failed');
      return r.json();
    }

    async function initDashboard() {
      try {
        const [summary, aimags, years] = await Promise.all([
          fetchJson('/api/summary'),
          fetchJson('/api/aimags'),
          fetchJson('/api/years')
        ]);

        document.getElementById('home-aimags').textContent = summary.aimag_count || 22;
        document.getElementById('home-records').textContent = Number(summary.record_count || 0).toLocaleString();
        document.getElementById('home-years').textContent = Math.max(1, (summary.year_end || 2022) - (summary.year_start || 2002) + 1);

        populateSelect(document.getElementById('filter-aimag'), aimags.aimags, { value: 'ALL', label: 'Бүх 22 аймаг' });
        populateSelect(document.getElementById('compare-a'), aimags.aimags, { value: '', label: 'Аймаг сонгох' });
        populateSelect(document.getElementById('compare-b'), aimags.aimags, { value: '', label: 'Аймаг сонгох' });
        populateSelect(document.getElementById('filter-start-year'), years.years, null);
        populateSelect(document.getElementById('filter-end-year'), years.years, null);
        populateSelect(document.getElementById('filter-year'), years.years, { value: 'ALL', label: 'Бүх он' });
        populateSelect(document.getElementById('filter-month'), [1,2,3,4,5,6,7,8,9,10,11,12], { value: 'ALL', label: 'Бүх сар' });
        populateSelect(document.getElementById('database-filter-aimag'), aimags.aimags, { value: 'ALL', label: 'Бүх аймаг' });
        populateSelect(document.getElementById('database-filter-year'), years.years, { value: 'ALL', label: 'Бүх он' });
        populateSelect(document.getElementById('database-filter-month'), [1,2,3,4,5,6,7,8,9,10,11,12], { value: 'ALL', label: 'Бүх сар' });
        populateSelect(document.getElementById('compare-start-year'), years.years, null);
        populateSelect(document.getElementById('compare-end-year'), years.years, null);

        document.getElementById('filter-start-year').value = 2002;
        document.getElementById('filter-end-year').value = 2022;
        document.getElementById('filter-year').value = 'ALL';
        document.getElementById('filter-month').value = 'ALL';
        document.getElementById('database-filter-year').value = 'ALL';
        document.getElementById('database-filter-month').value = 'ALL';
        document.getElementById('compare-start-year').value = 2002;
        document.getElementById('compare-end-year').value = 2022;

        document.getElementById('filter-aimag').addEventListener('change', () => {
          selectAimag(document.getElementById('filter-aimag').value);
        });

        document.getElementById('database-filter-aimag').addEventListener('change', () => {
          selectAimag(document.getElementById('database-filter-aimag').value);
        });

        document.getElementById('filter-year').addEventListener('change', () => {
          state.year = document.getElementById('filter-year').value;
          document.getElementById('database-filter-year').value = state.year;
          refreshAtlas();
          renderDatabaseTable();
          renderAimagMap();
        });

        document.getElementById('filter-month').addEventListener('change', () => {
          state.month = document.getElementById('filter-month').value;
          document.getElementById('database-filter-month').value = state.month;
          refreshAtlas();
          renderDatabaseTable();
          renderAimagMap();
        });

        document.getElementById('database-filter-year').addEventListener('change', () => {
          state.year = document.getElementById('database-filter-year').value;
          document.getElementById('filter-year').value = state.year;
          refreshAtlas();
          renderDatabaseTable();
          renderAimagMap();
        });

        document.getElementById('database-filter-month').addEventListener('change', () => {
          state.month = document.getElementById('database-filter-month').value;
          document.getElementById('filter-month').value = state.month;
          refreshAtlas();
          renderDatabaseTable();
          renderAimagMap();
        });

        document.getElementById('filter-start-year').addEventListener('change', () => {
          state.startYear = Number(document.getElementById('filter-start-year').value);
          refreshAtlas();
          renderDatabaseTable();
          renderAimagMap();
        });

        document.getElementById('filter-end-year').addEventListener('change', () => {
          state.endYear = Number(document.getElementById('filter-end-year').value);
          refreshAtlas();
          renderDatabaseTable();
          renderAimagMap();
        });

        document.getElementById('compare-a').addEventListener('change', renderCompareChart);
        document.getElementById('compare-b').addEventListener('change', renderCompareChart);
        document.getElementById('compare-start-year').addEventListener('change', renderCompareChart);
        document.getElementById('compare-end-year').addEventListener('change', renderCompareChart);

        const defaultA = aimags.aimags.find((name) => name === 'Arhangay') || aimags.aimags[0];
        const defaultB = aimags.aimags.find((name) => name === 'Hovd') || aimags.aimags[1] || aimags.aimags[0];
        if (defaultA) document.getElementById('compare-a').value = defaultA;
        if (defaultB) document.getElementById('compare-b').value = defaultB;

        refreshAtlas();
        renderCompareChart();
        renderDatabaseTable();
        renderGeopackageLayers();
        await renderAimagMap();
      } catch (error) {
        console.error(error);
      }
    }

    async function refreshAtlas() {
      const aimag = state.aimag === 'ALL' ? null : state.aimag;
      const params = new URLSearchParams({
        start_year: String(state.startYear),
        end_year: String(state.endYear)
      });
      if (state.aimags.length) params.set('aimags', state.aimags.join(','));
      else if (aimag) params.set('aimag', aimag);
      if (state.year && state.year !== 'ALL') params.set('year', String(state.year));
      if (state.month && state.month !== 'ALL') params.set('month', String(state.month));

      const [series, rows] = await Promise.all([
        fetchJson(`/api/series?${params.toString()}`),
        fetchJson(`/api/desert-data?${params.toString()}`)
      ]);
      const labels = series.labels || [];
      const values = series.values || [];

      const selectionLabel = state.regionName || aimag || 'Бүх аймаг';
      document.getElementById('atlas-selected').textContent = selectionLabel;
      const peak = values.length ? Math.max(...values) : 0;
      const avg = values.length ? (values.reduce((sum, v) => sum + v, 0) / values.length) : 0;
      document.getElementById('peak-value').textContent = state.regionName || aimag || 'Нийт';
      document.getElementById('peak-area').textContent = `${Number(peak).toLocaleString()} км²`;
      document.getElementById('latest-year').textContent = labels[labels.length - 1] || '—';
      document.getElementById('avg-area').textContent = `${Number(avg).toLocaleString()} км²`;

      const aimagAreas = new Map();
      rows.forEach(row => {
        const area = aimagAreas.get(row.aimag_name) || { total: 0, count: 0 };
        area.total += Number(row.desert_area_sqkm) || 0;
        area.count += 1;
        aimagAreas.set(row.aimag_name, area);
      });
      const aimagStats = Array.from(aimagAreas, ([name, area]) => ({
        name,
        mean: area.count ? area.total / area.count : 0
      }));
      const displayedStats = state.aimags.length
        ? aimagStats
        : state.aimag !== 'ALL'
          ? aimagStats
          : aimagStats.sort((a, b) => b.mean - a.mean).slice(0, 6);
      const regionList = document.getElementById('region-list');
      regionList.replaceChildren();
      displayedStats.forEach(({ name, mean }) => {
        const item = document.createElement('div');
        item.className = 'flex justify-between border-b border-desert-border pb-2';
        const label = document.createElement('span');
        label.textContent = name;
        const value = document.createElement('span');
        value.className = 'font-semibold text-accent-gold';
        value.textContent = `${mean.toLocaleString(undefined, { maximumFractionDigits: 2 })} км²`;
        item.append(label, value);
        regionList.appendChild(item);
      });

      const ctx = document.getElementById('atlas-chart');
      if (atlasChart) atlasChart.destroy();
      atlasChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: 'Цөлжилтийн талбай',
            data: values,
            borderColor: '#f59e0b',
            backgroundColor: 'rgba(245, 158, 11, 0.12)',
            borderWidth: 3,
            fill: true,
            tension: 0.35,
            pointRadius: 4,
            pointBackgroundColor: '#fbbf24'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color: '#d6c5ae' }, grid: { color: 'rgba(255,255,255,0.05)' } },
            y: { ticks: { color: '#d6c5ae' }, grid: { color: 'rgba(255,255,255,0.05)' } }
          }
        }
      });
    }

    async function renderCompareChart() {
      const a = document.getElementById('compare-a').value;
      const b = document.getElementById('compare-b').value;
      const start = Number(document.getElementById('compare-start-year').value || 2002);
      const end = Number(document.getElementById('compare-end-year').value || 2022);
      if (!a || !b) return;

      const [seriesA, seriesB] = await Promise.all([
        fetchJson(`/api/series?aimag=${encodeURIComponent(a)}&start_year=${start}&end_year=${end}`),
        fetchJson(`/api/series?aimag=${encodeURIComponent(b)}&start_year=${start}&end_year=${end}`)
      ]);

      const labels = seriesA.labels.length ? seriesA.labels : seriesB.labels;
      const valsA = labels.map((year) => {
        const idx = seriesA.labels.indexOf(year);
        return idx >= 0 ? seriesA.values[idx] : 0;
      });
      const valsB = labels.map((year) => {
        const idx = seriesB.labels.indexOf(year);
        return idx >= 0 ? seriesB.values[idx] : 0;
      });

      const ctx = document.getElementById('compare-chart');
      if (compareChart) compareChart.destroy();
      compareChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [
            { label: a, data: valsA, backgroundColor: '#f59e0b', borderRadius: 4 },
            { label: b, data: valsB, backgroundColor: '#14b8a6', borderRadius: 4 }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { labels: { color: '#f5f5f4' } } },
          scales: {
            x: { ticks: { color: '#d6c5ae' }, grid: { display: false } },
            y: { ticks: { color: '#d6c5ae' }, grid: { color: 'rgba(255,255,255,0.05)' } }
          }
        }
      });
    }

    async function renderDatabaseTable() {
      const params = new URLSearchParams({
        start_year: String(state.startYear),
        end_year: String(state.endYear)
      });
      if (state.aimags.length) params.set('aimags', state.aimags.join(','));
      else if (state.aimag && state.aimag !== 'ALL') params.set('aimag', state.aimag);
      if (state.year && state.year !== 'ALL') params.set('year', String(state.year));
      if (state.month && state.month !== 'ALL') params.set('month', String(state.month));
      databaseRows = await fetchJson(`/api/desert-data${params.toString() ? `?${params.toString()}` : ''}`);
      databasePage = 1;
      applyDatabaseFilters();
    }

    function selectAimag(aimag) {
      state.aimag = aimag || 'ALL';
      state.aimags = [];
      state.regionName = '';
      document.getElementById('filter-aimag').value = state.aimag;
      document.getElementById('database-filter-aimag').value = state.aimag;
      refreshAtlas();
      renderDatabaseTable();
      renderAimagMap();
    }

    function selectRegion(aimags, regionName) {
      state.aimag = 'ALL';
      state.aimags = aimags;
      state.regionName = regionName;
      document.getElementById('filter-aimag').value = 'ALL';
      document.getElementById('database-filter-aimag').value = 'ALL';
      refreshAtlas();
      renderDatabaseTable();
      renderAimagMap();
    }

    function aimagMapColor(area) {
      if (area < 1000) return '#6f412d';
      if (area < 4000) return '#a66839';
      if (area < 8000) return '#d97706';
      return '#ef4444';
    }

    function mapPoint([longitude, latitude]) {
      const [minX, minY, maxX, maxY] = aimagMapBounds;
      const width = 900;
      const height = 440;
      const scale = Math.min(width / (maxX - minX), height / (maxY - minY));
      const mapWidth = (maxX - minX) * scale;
      const mapHeight = (maxY - minY) * scale;
      const offsetX = (960 - mapWidth) / 2;
      const offsetY = (500 - mapHeight) / 2;
      return [
        offsetX + (longitude - minX) * scale,
        500 - offsetY - (latitude - minY) * scale
      ];
    }

    function geometryPath(geometry) {
      const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
      return polygons.map(rings => rings.map(ring => {
        return ring.map((point, index) => {
          const [x, y] = mapPoint(point);
          return `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(' ') + ' Z';
      }).join(' ')).join(' ');
    }

    async function renderAimagMap() {
      try {
        const params = new URLSearchParams({
          start_year: String(state.startYear),
          end_year: String(state.endYear)
        });
        if (state.year && state.year !== 'ALL') params.set('year', String(state.year));
        if (state.month && state.month !== 'ALL') params.set('month', String(state.month));

        const result = await fetchJson(`/api/aimag-map?${params.toString()}`);
        aimagMapFeatures = result.features || [];
        aimagMapBounds = result.bounds;
        if (!aimagMapBounds || !aimagMapFeatures.length) {
          throw new Error('No aimag boundary features were returned');
        }

        document.querySelectorAll('.aimag-map').forEach(map => {
          map.replaceChildren();
          aimagMapFeatures.forEach(feature => {
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', geometryPath(feature.geometry));
            path.setAttribute('fill', aimagMapColor(feature.area_sqkm));
            path.setAttribute('fill-rule', 'evenodd');
            const selected = state.aimag === feature.name || state.aimags.includes(feature.name);
            path.setAttribute('class', `aimag-map-path${selected ? ' selected' : ''}`);
            path.setAttribute('data-aimag', feature.name);
            path.setAttribute('tabindex', '0');
            path.setAttribute('role', 'button');
            path.setAttribute('aria-pressed', String(selected));
            path.setAttribute('aria-label', `${feature.name}: дундаж цөлжилтийн талбай ${Number(feature.area_sqkm).toLocaleString()} км²`);
            const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
            title.textContent = `${feature.name}: ${Number(feature.area_sqkm).toLocaleString()} км²`;
            path.appendChild(title);
            map.appendChild(path);

            const [labelX, labelY] = mapPoint(feature.label);
            const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            label.setAttribute('x', labelX.toFixed(1));
            label.setAttribute('y', labelY.toFixed(1));
            label.setAttribute('class', 'aimag-map-label');
            label.textContent = feature.name;
            map.appendChild(label);
          });
        });
        const selectedLabel = state.regionName || (state.aimag === 'ALL' ? 'Бүх аймаг' : state.aimag);
        document.getElementById('atlas-map-selected').textContent = selectedLabel;
        document.getElementById('database-map-selected').textContent = selectedLabel;
      } catch (error) {
        console.error('Aimag map loading failed:', error);
        document.querySelectorAll('.aimag-map').forEach(map => {
          map.replaceChildren();
          const message = document.createElementNS('http://www.w3.org/2000/svg', 'text');
          message.setAttribute('x', '480');
          message.setAttribute('y', '250');
          message.setAttribute('class', 'aimag-map-label');
          message.textContent = 'Аймгийн хил ачааллахад алдаа гарлаа.';
          map.appendChild(message);
        });
      }
    }

    function applyDatabaseFilters() {
      const query = document.getElementById('table-search').value.trim().toLocaleLowerCase();
      filteredDatabaseRows = databaseRows.filter(row =>
        [row.aimag_name, row.year, row.month, row.desert_area_sqkm]
          .some(value => String(value).toLocaleLowerCase().includes(query))
      );
      filteredDatabaseRows.sort((left, right) => {
        const a = left[databaseSort.column];
        const b = right[databaseSort.column];
        const comparison = typeof a === 'number' && typeof b === 'number'
          ? a - b
          : String(a).localeCompare(String(b), 'mn', { numeric: true, sensitivity: 'base' });
        return databaseSort.ascending ? comparison : -comparison;
      });
      renderDatabasePage();
    }

    function renderDatabasePage() {
      const body = document.getElementById('data-table-body');
      body.replaceChildren();

      const total = filteredDatabaseRows.length;
      const totalPages = Math.max(1, Math.ceil(total / databasePageSize));
      databasePage = Math.min(Math.max(databasePage, 1), totalPages);
      const start = (databasePage - 1) * databasePageSize;
      const pageRows = filteredDatabaseRows.slice(start, start + databasePageSize);

      if (pageRows.length === 0) {
        const row = body.insertRow();
        const cell = row.insertCell();
        cell.colSpan = 4;
        cell.className = 'p-6 text-center text-desert-400';
        cell.textContent = 'Тохирох өгөгдөл олдсонгүй.';
      } else {
        pageRows.forEach(record => {
          const row = body.insertRow();
          const values = [
            record.aimag_name,
            record.year,
            `${record.month}-р сар`,
            `${Number(record.desert_area_sqkm).toLocaleString()} км²`
          ];
          values.forEach((value, index) => {
            const cell = row.insertCell();
            cell.className = `p-3.5${index === 0 ? ' font-medium text-desert-100' : ''}${index === 3 ? ' font-mono text-accent-gold font-semibold' : ''}`;
            cell.textContent = String(value);
          });
          row.className = 'hover:bg-desert-card/80 transition';
        });
      }

      document.getElementById('table-count').textContent = `${total.toLocaleString()} мөр`;
      document.getElementById('pagination-info').textContent =
        `Үр дүн: ${total ? start + 1 : 0}-${Math.min(start + pageRows.length, total)} / нийт ${total.toLocaleString()}`;
      document.getElementById('page-number-display').textContent = `${databasePage} / ${totalPages}`;
      document.getElementById('btn-prev-page').disabled = databasePage === 1;
      document.getElementById('btn-next-page').disabled = databasePage === totalPages;
    }

    function sortDatabaseTable(column) {
      if (!['aimag_name', 'year', 'month', 'desert_area_sqkm'].includes(column)) return;
      databaseSort = {
        column,
        ascending: databaseSort.column === column ? !databaseSort.ascending : true
      };
      databasePage = 1;
      applyDatabaseFilters();
    }

    function changeDatabasePage(offset) {
      databasePage += offset;
      renderDatabasePage();
    }

    function exportDatabaseCsv() {
      const columns = [
        ['aimag_name', 'Аймаг'],
        ['year', 'Он'],
        ['month', 'Сар'],
        ['desert_area_sqkm', 'Цөлжсөн талбай (км²)']
      ];
      const escapeCsv = value => `"${String(value ?? '').replaceAll('"', '""')}"`;
      const content = [
        columns.map(([, label]) => escapeCsv(label)).join(','),
        ...filteredDatabaseRows.map(row => columns.map(([key]) => escapeCsv(row[key])).join(','))
      ].join('\\r\\n');
      const url = URL.createObjectURL(new Blob(['\\uFEFF', content], { type: 'text/csv;charset=utf-8' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = 'mongolia_desert_monthly_aimags.csv';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    }

    async function renderGeopackageLayers() {
      const status = document.getElementById('geopackage-status');
      const list = document.getElementById('geopackage-layers');
      try {
        const summary = await fetchJson('/api/geopackage');
        list.replaceChildren();
        if (!summary.layers.length) {
          status.textContent = 'Давхарга олдсонгүй';
          return;
        }
        summary.layers.forEach(layer => {
          const item = document.createElement('li');
          item.className = 'rounded-xl border border-desert-border/60 bg-desert-card px-4 py-3 flex items-center';
          const icon = document.createElement('i');
          icon.className = 'fa-solid fa-map text-accent-gold mr-2.5';
          const name = document.createElement('span');
          name.textContent = layer;
          item.append(icon, name);
          list.appendChild(item);
        });
        status.textContent = `${summary.count} давхарга`;
      } catch (error) {
        status.textContent = 'Давхаргыг уншиж чадсангүй';
        console.error('GeoPackage layer loading failed:', error);
      }
    }

    initDashboard();
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    return HTML_PAGE


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
