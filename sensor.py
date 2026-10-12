"""Indeks kekasaran jalan dari data akselerometer HP (CSV dari phyphox, Physics Toolbox, dsb.).

Kekasaran dihitung sebagai RMS percepatan vertikal per segmen setelah rata-rata (termasuk gravitasi) dibuang.
Ini BUKAN IRI resmi: angkanya hanya bisa dibandingkan antar-rekaman dengan kendaraan, kecepatan, dan posisi HP yang sama.
"""
import io
import math
import statistics
from typing import Optional

import pandas as pd

from statistik import meter_ke_sta

MIN_SAMPEL = 10


def baca_csv(data: bytes) -> pd.DataFrame:
    """Baca CSV (pemisah koma/titik koma/tab), ambil kolom yang berisi angka saja."""
    df = pd.read_csv(io.BytesIO(data), sep=None, engine="python")
    df = df.apply(lambda s: pd.to_numeric(s.astype(str).str.replace(",", ".", regex=False), errors="coerce"))
    return df.dropna(axis=1, how="all")


def tebak_kolom(kolom: list[str]) -> dict:
    """Tebak kolom waktu, percepatan vertikal (z), lintang, dan bujur dari nama kolom."""
    kecil = {k: k.lower() for k in kolom}

    def cari(*kata, kecuali=()):
        return next((k for k, v in kecil.items() if any(w in v for w in kata) and not any(x in v for x in kecuali)), None)

    return {
        "waktu": cari("time", "waktu", "timestamp") or (kolom[0] if kolom else None),
        "az": cari("accel z", "acceleration z", "az", "gfz", "z (m/s", "_z", " z"),
        "lat": cari("lat"),
        "lon": cari("lon", "lng", "bujur", kecuali=("long_", "longitudinal")),
    }


def _haversine(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def kekasaran_per_segmen(df: pd.DataFrame, kol_waktu: str, kol_az: str, panjang_m: float,
                         kecepatan_kmh: Optional[float] = None, kol_lat: Optional[str] = None,
                         kol_lon: Optional[str] = None, sta_awal_m: float = 0.0) -> list[dict]:
    """Bagi rekaman jadi segmen sepanjang `panjang_m` dan hitung RMS percepatan vertikal tiap segmen.

    Jarak dihitung dari GPS bila kolom lat/lon diberikan, selain itu dari waktu × kecepatan tetap.
    """
    if panjang_m <= 0:
        raise ValueError("Panjang segmen harus lebih dari 0 m.")
    pakai_gps = bool(kol_lat and kol_lon)
    kolom = [kol_waktu, kol_az] + ([kol_lat, kol_lon] if pakai_gps else [])
    d = df[kolom].dropna(subset=[kol_waktu, kol_az]).sort_values(kol_waktu).reset_index(drop=True)
    if d.empty:
        raise ValueError("Tidak ada data waktu dan percepatan yang terbaca.")

    if pakai_gps:
        d[[kol_lat, kol_lon]] = d[[kol_lat, kol_lon]].ffill().bfill()
        if d[kol_lat].isna().all():
            raise ValueError("Kolom lintang/bujur kosong.")
        lat, lon = d[kol_lat].to_numpy(), d[kol_lon].to_numpy()
        jarak = [0.0]
        for i in range(1, len(d)):
            jarak.append(jarak[-1] + _haversine(lat[i - 1], lon[i - 1], lat[i], lon[i]))
        d["jarak"] = jarak
    else:
        if not kecepatan_kmh or kecepatan_kmh <= 0:
            raise ValueError("Isi kecepatan kendaraan, atau pilih kolom lintang/bujur.")
        d["jarak"] = (d[kol_waktu] - d[kol_waktu].iloc[0]) * kecepatan_kmh / 3.6

    d["segmen"] = (d["jarak"] // panjang_m).astype(int)
    hasil = []
    for s, g in d.groupby("segmen"):
        if len(g) < MIN_SAMPEL:
            continue
        a = g[kol_az] - g[kol_az].mean()
        r = {"sta": meter_ke_sta(sta_awal_m + s * panjang_m), "jarak_awal_m": round(s * panjang_m, 1),
             "sampel": len(g), "rms": float(math.sqrt((a ** 2).mean())), "puncak": float(a.abs().max())}
        if pakai_gps:
            r["lat"], r["lon"] = float(g[kol_lat].mean()), float(g[kol_lon].mean())
        hasil.append(r)
    if hasil:
        median = statistics.median(r["rms"] for r in hasil) or 1.0
        for r in hasil:
            r["relatif"] = r["rms"] / median
    return hasil
