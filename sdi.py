"""Perhitungan Surface Distress Index (Bina Marga, Panduan Survai Kondisi Jalan SMD-03/RCS)."""
from dataclasses import dataclass

LEBAR_OPSI = ["tidak ada", "<1 mm", "1-3 mm", ">3 mm"]
ALUR_OPSI = ["tidak ada", "<1 cm", "1-3 cm", ">3 cm"]
ALUR_X = {"tidak ada": 0, "<1 cm": 0.5, "1-3 cm": 2, ">3 cm": 4}


@dataclass(frozen=True)
class Kelas:
    batas: float  # SDI < batas
    label: str
    warna: str
    latar: str
    rentang: str
    tindakan: str


KELAS = [
    Kelas(50, "Baik", "#2f7d46", "#e2f1e6", "< 50", "Pemeliharaan rutin"),
    Kelas(100, "Sedang", "#a48400", "#f5efcc", "50–100", "Pemeliharaan rutin, pantau perkembangan"),
    Kelas(150, "Rusak ringan", "#c3561b", "#f8e3d6", "100–150", "Pemeliharaan berkala (pelapisan ulang / overlay tipis)"),
    Kelas(float("inf"), "Rusak berat", "#b3261e", "#f6dcd9", "≥ 150", "Rehabilitasi atau rekonstruksi"),
]


def kelas_dari_label(label: str) -> Kelas:
    return next((k for k in KELAS if k.label == label), KELAS[0])


def kelas_dari_sdi(sdi: float) -> Kelas:
    return next((k for k in KELAS if sdi < k.batas), KELAS[-1])


@dataclass(frozen=True)
class SDIResult:
    sdi1: float
    sdi2: float
    add_l: float
    sdi3: float
    add_a: float
    sdi: float
    per100: float
    kelas: Kelas


def _angka(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def compute_sdi(retak, lebar, lubang, alur, panjang) -> SDIResult:
    a = max(0.0, _angka(retak))
    sdi1 = 0 if a == 0 else 5 if a < 10 else 20 if a <= 30 else 40
    sdi2 = sdi1 * 2 if lebar == ">3 mm" else sdi1
    p = _angka(panjang) or 100
    per100 = max(0.0, _angka(lubang)) * 100 / max(1.0, p)
    add_l = 0 if per100 == 0 else 15 if per100 < 10 else 75 if per100 <= 50 else 225
    sdi3 = sdi2 + add_l
    add_a = 5 * ALUR_X.get(alur, 0)
    sdi = sdi3 + add_a
    return SDIResult(sdi1, sdi2, add_l, sdi3, add_a, sdi, per100, kelas_dari_sdi(sdi))


def fmt_sdi(sdi: float) -> str:
    return str(int(sdi)) if float(sdi).is_integer() else f"{sdi:.1f}"
