import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sdi import compute_sdi, kelas_dari_sdi  # noqa: E402
from storage import EXAMPLE_LOG, load_log, save_log, to_csv, to_geojson  # noqa: E402


def test_contoh_sedang():
    s = compute_sdi(12, "1-3 mm", 2, "tidak ada", 20)
    assert s.per100 == 10
    assert (s.sdi1, s.sdi2, s.add_l, s.add_a) == (20, 20, 75, 0)
    assert s.sdi == 95 and s.kelas.label == "Sedang"


def test_contoh_rusak_berat():
    s = compute_sdi(45, "1-3 mm", 18, "tidak ada", 30)
    assert s.per100 == 60
    assert s.sdi == 265 and s.kelas.label == "Rusak berat"


def test_lebar_besar_menggandakan():
    assert compute_sdi(5, ">3 mm", 0, "tidak ada", 100).sdi == 10
    assert compute_sdi(31, ">3 mm", 0, "tidak ada", 100).sdi == 80


def test_alur_roda():
    assert compute_sdi(0, "tidak ada", 0, ">3 cm", 100).add_a == 20
    assert compute_sdi(0, "tidak ada", 0, "<1 cm", 100).add_a == 2.5


def test_ambang_lubang():
    assert compute_sdi(0, "tidak ada", 9, "tidak ada", 100).add_l == 15
    assert compute_sdi(0, "tidak ada", 50, "tidak ada", 100).add_l == 75
    assert compute_sdi(0, "tidak ada", 51, "tidak ada", 100).add_l == 225


def test_batas_kelas():
    assert kelas_dari_sdi(49.9).label == "Baik"
    assert kelas_dari_sdi(50).label == "Sedang"
    assert kelas_dari_sdi(100).label == "Rusak ringan"
    assert kelas_dari_sdi(150).label == "Rusak berat"


def test_input_kosong_aman():
    s = compute_sdi("", "tidak ada", None, "?", 0)
    assert s.sdi == 0 and s.kelas.label == "Baik"


def test_contoh_log_konsisten():
    for r in EXAMPLE_LOG:
        assert kelas_dari_sdi(r["sdi"]).label == r["cls"]


def test_csv_dan_geojson():
    rows = EXAMPLE_LOG + [{"ruas": 'Jl. "A"', "sta": "0+000", "panjang": 10, "retak": 0, "per100": 0,
                           "sdi": 0, "cls": "Baik", "lat": None, "lon": None, "tgl": "2026-10-12"}]
    parsed = list(csv.reader(io.StringIO(to_csv(rows))))
    assert parsed[0][0] == "ruas" and len(parsed) == len(rows) + 1
    assert parsed[-1][0] == 'Jl. "A"' and parsed[-1][7] == ""
    fc = to_geojson(rows)
    assert len(fc["features"]) == len(EXAMPLE_LOG)
    assert fc["features"][0]["geometry"]["coordinates"] == [107.60895, -6.91432]


def test_simpan_muat(tmp_path):
    p = tmp_path / "data" / "segmen.json"
    assert load_log(p) == []
    save_log(EXAMPLE_LOG[:2], p)
    assert load_log(p) == EXAMPLE_LOG[:2]
