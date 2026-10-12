"""Statistik Gaussian untuk daftar segmen: pemulusan sepanjang STA dan deteksi segmen aneh (z-score)."""
import math
import statistics
from typing import Optional

SIGMA_M = 50.0  # simpangan baku kernel Gaussian dalam meter
AMBANG_Z = 2.0  # |z| di atas nilai ini ditandai sebagai segmen aneh
MIN_N_RUAS = 3  # minimal jumlah segmen per ruas agar statistik bermakna


def sta_ke_meter(sta: str) -> Optional[float]:
    """'2+100' (km+m) -> 2100.0. Kembalikan None bila format tidak dikenali."""
    try:
        km, m = str(sta).split("+")
        return int(km) * 1000 + float(m)
    except (ValueError, TypeError):
        return None


def pemulusan_gaussian(rows: list[dict], sigma_m: float = SIGMA_M) -> list[Optional[float]]:
    """SDI yang dihaluskan dengan kernel Gaussian, hanya dari segmen dalam ruas yang sama.

    Satu nilai per baris, urutan sama dengan `rows`. None bila STA tidak bisa dibaca.
    """
    posisi = [sta_ke_meter(r.get("sta")) for r in rows]
    hasil: list[Optional[float]] = []
    for i, (p_i, r_i) in enumerate(zip(posisi, rows)):
        if p_i is None:
            hasil.append(None)
            continue
        bobot_total = bobot_sdi = 0.0
        for p_j, r_j in zip(posisi, rows):
            if p_j is None or r_j.get("ruas") != r_i.get("ruas"):
                continue
            w = math.exp(-((p_j - p_i) ** 2) / (2 * sigma_m ** 2))
            bobot_total += w
            bobot_sdi += w * float(r_j["sdi"])
        hasil.append(bobot_sdi / bobot_total if bobot_total else None)
    return hasil


def statistik_ruas(rows: list[dict]) -> list[dict]:
    """Per ruas: jumlah segmen, rata-rata SDI, simpangan baku, dan interval kepercayaan 95% rata-rata."""
    per_ruas: dict[str, list[float]] = {}
    for r in rows:
        per_ruas.setdefault(r.get("ruas") or "–", []).append(float(r["sdi"]))
    out = []
    for ruas, nilai in per_ruas.items():
        n = len(nilai)
        rata = statistics.fmean(nilai)
        sb = statistics.stdev(nilai) if n > 1 else 0.0
        galat = 1.96 * sb / math.sqrt(n) if n > 1 else 0.0
        out.append({"ruas": ruas, "n": n, "rata": rata, "sb": sb,
                    "ci_bawah": rata - galat, "ci_atas": rata + galat})
    return out


def skor_z(rows: list[dict], ambang: float = AMBANG_Z) -> list[Optional[float]]:
    """z-score SDI tiap segmen terhadap rata-rata ruasnya. None bila ruas punya kurang dari MIN_N_RUAS segmen
    atau simpangan bakunya nol."""
    per_ruas: dict[str, list[float]] = {}
    for r in rows:
        per_ruas.setdefault(r.get("ruas") or "–", []).append(float(r["sdi"]))
    stat = {ruas: (statistics.fmean(v), statistics.stdev(v))
            for ruas, v in per_ruas.items() if len(v) >= MIN_N_RUAS}
    hasil: list[Optional[float]] = []
    for r in rows:
        ruas = r.get("ruas") or "–"
        if ruas not in stat or stat[ruas][1] == 0:
            hasil.append(None)
            continue
        rata, sb = stat[ruas]
        hasil.append((float(r["sdi"]) - rata) / sb)
    return hasil


def segmen_aneh(rows: list[dict], ambang: float = AMBANG_Z) -> list[bool]:
    return [z is not None and abs(z) > ambang for z in skor_z(rows, ambang)]
