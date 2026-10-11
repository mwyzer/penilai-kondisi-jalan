"""Penyimpanan daftar segmen (data/segmen.json) dan ekspor CSV / GeoJSON."""
import csv
import io
import json
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "segmen.json"

EXAMPLE_LOG = [
    {"ruas": "Jl. Contoh Raya", "sta": "1+900", "panjang": 100, "retak": 0, "per100": 0, "sdi": 0, "cls": "Baik", "lat": -6.91432, "lon": 107.60895, "tgl": "2026-10-10"},
    {"ruas": "Jl. Contoh Raya", "sta": "2+000", "panjang": 50, "retak": 4, "per100": 0, "sdi": 5, "cls": "Baik", "lat": -6.91470, "lon": 107.60980, "tgl": "2026-10-10"},
    {"ruas": "Jl. Contoh Raya", "sta": "2+050", "panjang": 25, "retak": 22, "per100": 4, "sdi": 35, "cls": "Baik", "lat": -6.91490, "lon": 107.61022, "tgl": "2026-10-10"},
    {"ruas": "Jl. Contoh Raya", "sta": "2+075", "panjang": 25, "retak": 35, "per100": 12, "sdi": 115, "cls": "Rusak ringan", "lat": -6.91500, "lon": 107.61043, "tgl": "2026-10-10"},
    {"ruas": "Jl. Contoh Raya", "sta": "2+100", "panjang": 20, "retak": 12, "per100": 10, "sdi": 95, "cls": "Sedang", "lat": -6.91511, "lon": 107.61064, "tgl": "2026-10-10"},
    {"ruas": "Jl. Contoh Raya", "sta": "2+120", "panjang": 30, "retak": 45, "per100": 60, "sdi": 265, "cls": "Rusak berat", "lat": -6.91528, "lon": 107.61093, "tgl": "2026-10-10"},
]

CSV_HEAD = ["ruas", "sta", "panjang_m", "retak_persen", "lubang_per_100m", "sdi", "kondisi", "lat", "lon", "waktu_foto", "tanggal"]


def load_log(path: Path = DATA_FILE) -> list[dict]:
    try:
        v = json.loads(path.read_text(encoding="utf-8"))
        return v if isinstance(v, list) else []
    except (OSError, ValueError):
        return []


def save_log(log: list[dict], path: Path = DATA_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")


def _kosong(v):
    return "" if v is None else v


def to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\n")
    w.writerow(CSV_HEAD)
    for r in rows:
        w.writerow([r.get("ruas"), r.get("sta"), r.get("panjang"), r.get("retak"), r.get("per100"), r.get("sdi"),
                    r.get("cls"), _kosong(r.get("lat")), _kosong(r.get("lon")), r.get("waktu_foto") or "", r.get("tgl")])
    return buf.getvalue()


def to_geojson(rows: list[dict]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(r["lon"]), float(r["lat"])]},
                "properties": {
                    "ruas": r.get("ruas"), "sta": r.get("sta"), "panjang_m": r.get("panjang"),
                    "retak_persen": r.get("retak"), "lubang_per_100m": r.get("per100"), "sdi": r.get("sdi"),
                    "kondisi": r.get("cls"), "waktu_foto": r.get("waktu_foto") or "", "tanggal": r.get("tgl"),
                },
            }
            for r in rows
            if r.get("lat") is not None and r.get("lon") is not None
        ],
    }
