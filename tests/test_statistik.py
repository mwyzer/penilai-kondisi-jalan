import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from statistik import pemulusan_gaussian, segmen_aneh, skor_z, sta_ke_meter, statistik_ruas  # noqa: E402
from storage import EXAMPLE_LOG  # noqa: E402


def _seg(ruas, sta, sdi):
    return {"ruas": ruas, "sta": sta, "sdi": sdi}


@pytest.mark.parametrize("sta, m", [("2+100", 2100.0), ("0+000", 0.0), ("10+50.5", 10050.5)])
def test_sta_ke_meter(sta, m):
    assert sta_ke_meter(sta) == m


@pytest.mark.parametrize("sta", ["2100", "a+b", "", None])
def test_sta_tidak_valid(sta):
    assert sta_ke_meter(sta) is None


def test_pemulusan_segmen_tunggal_sama_dengan_nilainya():
    assert pemulusan_gaussian([_seg("A", "1+000", 80)]) == [pytest.approx(80)]


def test_pemulusan_menjaga_ruas_terpisah():
    rows = [_seg("A", "1+000", 10), _seg("B", "1+000", 200)]
    assert pemulusan_gaussian(rows) == [pytest.approx(10), pytest.approx(200)]


def test_pemulusan_di_antara_dua_nilai_berada_di_rentangnya():
    rows = [_seg("A", "1+000", 10), _seg("A", "1+050", 100), _seg("A", "1+100", 10)]
    tengah = pemulusan_gaussian(rows)[1]
    assert 10 < tengah < 100


def test_pemulusan_sta_tidak_valid_jadi_none():
    rows = [_seg("A", "xx", 10), _seg("A", "1+000", 20)]
    assert pemulusan_gaussian(rows)[0] is None


def test_statistik_ruas():
    rows = [_seg("A", "1+000", 50), _seg("A", "1+010", 60), _seg("A", "1+020", 70), _seg("B", "1+000", 99)]
    a = next(s for s in statistik_ruas(rows) if s["ruas"] == "A")
    assert a["n"] == 3 and a["rata"] == pytest.approx(60) and a["sb"] == pytest.approx(10)
    assert a["ci_bawah"] < 60 < a["ci_atas"]
    b = next(s for s in statistik_ruas(rows) if s["ruas"] == "B")
    assert b["n"] == 1 and b["sb"] == 0


def test_z_score_butuh_minimal_tiga_segmen():
    assert skor_z([_seg("A", "1+000", 10), _seg("A", "1+010", 90)]) == [None, None]


def test_segmen_aneh_terdeteksi():
    nilai = [50, 52, 48, 51, 49, 50, 300]
    rows = [_seg("A", f"1+{i * 10:03d}", v) for i, v in enumerate(nilai)]
    aneh = segmen_aneh(rows)
    assert aneh[-1] is True and not any(aneh[:-1])


def test_segmen_seragam_tidak_aneh():
    rows = [_seg("A", f"1+{i * 10:03d}", 50) for i in range(5)]
    assert segmen_aneh(rows) == [False] * 5


def test_contoh_log_tidak_error():
    assert len(pemulusan_gaussian(EXAMPLE_LOG)) == len(EXAMPLE_LOG)
    assert len(segmen_aneh(EXAMPLE_LOG)) == len(EXAMPLE_LOG)
