import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analisis import HasilAnalisis  # noqa: E402
from impor import dari_berkas, dari_csv, dari_geojson  # noqa: E402
from sensor import baca_csv, kekasaran_per_segmen, tebak_kolom  # noqa: E402
from statistik import meter_ke_sta  # noqa: E402
from storage import EXAMPLE_LOG, to_csv, to_geojson  # noqa: E402
from video import VideoGagal, ambil_frame, gabung_hasil  # noqa: E402


# ---------- statistik.meter_ke_sta ----------
@pytest.mark.parametrize("m, sta", [(0, "0+000"), (2100, "2+100"), (10050.4, "10+050"), (-5, "0+000")])
def test_meter_ke_sta(m, sta):
    assert meter_ke_sta(m) == sta


# ---------- video ----------
def _buat_video(path: Path, frames: int = 60) -> bytes:
    tulis = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30, (320, 240))
    for i in range(frames):
        img = np.full((240, 320, 3), 90, np.uint8)
        cv2.putText(img, str(i), (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 255, 255), 5)
        tulis.write(img)
    tulis.release()
    return path.read_bytes()


def test_ambil_frame(tmp_path):
    data = _buat_video(tmp_path / "uji.avi")
    frames = ambil_frame(data, 4, "uji.avi")
    assert len(frames) == 4
    detik = [d for d, _ in frames]
    assert detik == sorted(detik) and 0 <= detik[0] and detik[-1] < 2.0
    assert all(b[:2] == b"\xff\xd8" for _, b in frames)  # JPEG


def test_video_rusak():
    with pytest.raises(VideoGagal):
        ambil_frame(b"bukan video", 3, "x.mp4")


def _hasil(**kw):
    dasar = dict(jalan_terlihat=True, jenis_perkerasan="aspal", deskripsi="d", kerusakan=[], luas_retak_persen=10,
                 lebar_retak="<1 mm", jumlah_lubang=0, kedalaman_alur="tidak ada", keyakinan=0.6, rekomendasi="r")
    return HasilAnalisis(**{**dasar, **kw})


def test_gabung_hasil():
    g = gabung_hasil([
        _hasil(luas_retak_persen=10, lebar_retak="<1 mm", jumlah_lubang=1, kedalaman_alur="tidak ada"),
        _hasil(luas_retak_persen=30, lebar_retak="1-3 mm", jumlah_lubang=3, kedalaman_alur="1-3 cm", rekomendasi="buruk"),
        _hasil(luas_retak_persen=20, lebar_retak="1-3 mm", jumlah_lubang=2, kedalaman_alur="<1 cm"),
        _hasil(jalan_terlihat=False, luas_retak_persen=99, jumlah_lubang=9),  # diabaikan
    ])
    assert g.luas_retak_persen == pytest.approx(20)
    assert g.lebar_retak == "1-3 mm" and g.kedalaman_alur == "<1 cm"
    assert g.jumlah_lubang == 3 and g.rekomendasi == "buruk"


def test_gabung_tanpa_jalan():
    assert gabung_hasil([_hasil(jalan_terlihat=False)]) is None
    assert gabung_hasil([]) is None


# ---------- impor ----------
def test_impor_bolak_balik_csv_dan_geojson():
    rows, galat = dari_csv(to_csv(EXAMPLE_LOG).encode())
    assert not galat and len(rows) == len(EXAMPLE_LOG)
    assert [r["sdi"] for r in rows] == [r["sdi"] for r in EXAMPLE_LOG]
    assert [r["cls"] for r in rows] == [r["cls"] for r in EXAMPLE_LOG]
    rows_g, galat_g = dari_geojson(json.dumps(to_geojson(EXAMPLE_LOG)).encode())
    assert not galat_g and rows_g[0]["lat"] == EXAMPLE_LOG[0]["lat"] and rows_g[0]["lon"] == EXAMPLE_LOG[0]["lon"]


def test_impor_csv_titik_koma_dan_baris_rusak():
    teks = "Ruas;STA;SDI;lat;lon\nJl. A;0+000;120,5;-6.9;107.6\nJl. A;;10;;\nJl. B;0+100;abc;;\n"
    rows, galat = dari_csv(teks.encode())
    assert len(rows) == 1 and len(galat) == 2
    assert rows[0]["sdi"] == 120.5 and rows[0]["cls"] == "Rusak ringan" and rows[0]["lat"] == -6.9


def test_impor_kolom_wajib_hilang():
    rows, galat = dari_csv(b"nama,nilai\nx,1\n")
    assert rows == [] and "Kolom wajib" in galat[0]


def test_impor_berdasarkan_ekstensi():
    assert dari_berkas("x.geojson", b"{}")[1] == ["Tidak ada 'features' di GeoJSON"]


# ---------- sensor ----------
def _rekaman(detik=60, hz=100, kasar_mulai=30):
    t = np.arange(0, detik, 1 / hz)
    rng = np.random.default_rng(0)
    az = 9.81 + rng.normal(0, 0.2, t.size)
    az[t >= kasar_mulai] += rng.normal(0, 1.5, (t >= kasar_mulai).sum())  # separuh akhir lebih kasar
    return pd.DataFrame({"Time (s)": t, "Linear Acceleration z (m/s^2)": az})


def test_kekasaran_dengan_kecepatan_tetap():
    hasil = kekasaran_per_segmen(_rekaman(), "Time (s)", "Linear Acceleration z (m/s^2)", 100, kecepatan_kmh=36)
    assert [r["sta"] for r in hasil] == [f"0+{i * 100:03d}" for i in range(6)]  # 36 km/jam × 60 s = 600 m
    halus, kasar = hasil[:3], hasil[3:]
    assert max(r["rms"] for r in halus) < min(r["rms"] for r in kasar)
    assert all(r["rms"] < 1.0 for r in halus)  # gravitasi sudah dibuang


def test_kekasaran_dengan_gps():
    df = _rekaman(detik=20, kasar_mulai=99)
    df["lat"] = -6.9
    df["lon"] = 107.6 + np.linspace(0, 0.0018, len(df))  # ±200 m ke timur
    hasil = kekasaran_per_segmen(df, "Time (s)", "Linear Acceleration z (m/s^2)", 50, kol_lat="lat", kol_lon="lon")
    assert 3 <= len(hasil) <= 5 and "lat" in hasil[0]


def test_kekasaran_tanpa_kecepatan_atau_gps():
    with pytest.raises(ValueError):
        kekasaran_per_segmen(_rekaman(), "Time (s)", "Linear Acceleration z (m/s^2)", 100)


def test_baca_csv_dan_tebak_kolom():
    teks = "time;gFx;gFy;gFz;Latitude;Longitude\n0,00;0,1;0,0;1,02;-6.9;107.6\n0,01;0,1;0,0;0,98;-6.9;107.6\n"
    df = baca_csv(teks.encode())
    assert df["gFz"].tolist() == [1.02, 0.98]
    tebak = tebak_kolom(list(df.columns))
    assert tebak == {"waktu": "time", "az": "gFz", "lat": "Latitude", "lon": "Longitude"}
    assert not math.isnan(df["time"].iloc[1])
