"""Impor data segmen dari CSV atau GeoJSON (format sama dengan ekspor aplikasi ini)."""
import csv
import io
import json
from datetime import date
from typing import Optional, Union

from sdi import kelas_dari_sdi

KOLOM_WAJIB = ["ruas", "sta", "sdi"]


def _angka(v, default: Optional[float] = None) -> Optional[float]:
    if v is None or str(v).strip() == "":
        return default
    try:
        return float(str(v).strip().replace(",", "."))
    except ValueError:
        return default


def _rapikan(x: float) -> Union[int, float]:
    return int(x) if float(x).is_integer() else round(x, 2)


def _baris(p: dict, lat=None, lon=None) -> Union[dict, str]:
    """Ubah satu baris/properti jadi segmen. Kembalikan pesan galat (str) bila tidak valid."""
    p = {str(k).strip().lower(): v for k, v in p.items()}
    ruas, sta, sdi = str(p.get("ruas") or "").strip(), str(p.get("sta") or "").strip(), _angka(p.get("sdi"))
    if not ruas or not sta:
        return "kolom ruas/sta kosong"
    if sdi is None or sdi < 0:
        return f"SDI tidak valid ({p.get('sdi')!r})"
    lat = _angka(p.get("lat")) if lat is None else lat
    lon = _angka(p.get("lon")) if lon is None else lon
    if lat is not None and lon is not None and not (abs(lat) <= 90 and abs(lon) <= 180):
        lat = lon = None
    return {
        "ruas": ruas, "sta": sta,
        "panjang": _rapikan(_angka(p.get("panjang_m", p.get("panjang")), 0) or 0),
        "retak": _rapikan(_angka(p.get("retak_persen", p.get("retak")), 0) or 0),
        "per100": _rapikan(_angka(p.get("lubang_per_100m", p.get("per100")), 0) or 0),
        "sdi": _rapikan(sdi), "cls": kelas_dari_sdi(sdi).label,  # kelas dihitung ulang dari SDI
        "lat": lat if lon is not None else None, "lon": lon if lat is not None else None,
        "waktu_foto": str(p.get("waktu_foto") or ""),
        "tgl": str(p.get("tanggal") or p.get("tgl") or date.today().isoformat()),
    }


def _kumpulkan(items) -> tuple[list[dict], list[str]]:
    rows, galat = [], []
    for nomor, (p, lat, lon) in enumerate(items, start=1):
        r = _baris(p, lat, lon)
        if isinstance(r, str):
            galat.append(f"Baris {nomor}: {r}")
        else:
            rows.append(r)
    return rows, galat


def dari_csv(data: bytes) -> tuple[list[dict], list[str]]:
    teks = data.decode("utf-8-sig", errors="replace")
    try:
        dialek = csv.Sniffer().sniff(teks[:4096], delimiters=",;\t")
    except csv.Error:
        dialek = csv.excel
    reader = csv.DictReader(io.StringIO(teks), dialect=dialek)
    kolom = {str(k).strip().lower() for k in (reader.fieldnames or [])}
    kurang = [k for k in KOLOM_WAJIB if k not in kolom]
    if kurang:
        return [], [f"Kolom wajib tidak ada: {', '.join(kurang)}"]
    return _kumpulkan((row, None, None) for row in reader)


def dari_geojson(data: bytes) -> tuple[list[dict], list[str]]:
    try:
        obj = json.loads(data.decode("utf-8-sig"))
    except ValueError:
        return [], ["Berkas bukan JSON yang valid"]
    fitur = obj.get("features", []) if isinstance(obj, dict) else []
    if not fitur:
        return [], ["Tidak ada 'features' di GeoJSON"]

    def item(f):
        geom = f.get("geometry") or {}
        lat = lon = None
        if geom.get("type") == "Point" and len(geom.get("coordinates") or []) >= 2:
            lon, lat = (_angka(v) for v in geom["coordinates"][:2])
        return f.get("properties") or {}, lat, lon

    return _kumpulkan(item(f) for f in fitur)


def dari_berkas(nama: str, data: bytes) -> tuple[list[dict], list[str]]:
    if nama.lower().endswith((".geojson", ".json")):
        return dari_geojson(data)
    return dari_csv(data)
