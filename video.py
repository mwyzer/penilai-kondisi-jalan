"""Input video pendek: ambil frame paling tajam, lalu gabungkan hasil analisis tiap frame jadi satu nilai segmen."""
import os
import statistics
import tempfile
from collections import Counter
from io import BytesIO
from typing import Optional

import cv2
from PIL import Image

from analisis import HasilAnalisis
from sdi import ALUR_OPSI, LEBAR_OPSI

KANDIDAT_PER_JENDELA = 5  # frame yang dibandingkan ketajamannya di tiap bagian video


class VideoGagal(Exception):
    pass


def _ketajaman(frame) -> float:
    """Variansi Laplacian: makin besar, makin tajam (tidak blur)."""
    return cv2.Laplacian(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()


def ambil_frame(data: bytes, jumlah: int = 5, nama: str = "video.mp4") -> list[tuple[float, bytes]]:
    """Bagi video jadi `jumlah` bagian yang sama panjang dan ambil frame paling tajam dari tiap bagian.

    Kembalikan daftar (detik, JPEG bytes).
    """
    akhiran = os.path.splitext(nama)[1].lower() or ".mp4"
    fd, path = tempfile.mkstemp(suffix=akhiran)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            raise VideoGagal("Video tidak bisa dibaca. Coba format MP4 (H.264) atau MOV dari kamera HP.")
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        if n <= 0:
            raise VideoGagal("Video kosong atau rusak.")
        jumlah = max(1, min(jumlah, n))
        hasil = []
        for i in range(jumlah):
            awal, akhir = i * n // jumlah, max(i * n // jumlah + 1, (i + 1) * n // jumlah)
            calon = sorted({awal + (akhir - awal) * (2 * j + 1) // (2 * KANDIDAT_PER_JENDELA)
                            for j in range(KANDIDAT_PER_JENDELA)})
            terbaik = None
            for idx in calon:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ok, frame = cap.read()
                if not ok:
                    continue
                skor = _ketajaman(frame)
                if terbaik is None or skor > terbaik[0]:
                    terbaik = (skor, idx, frame)
            if terbaik:
                buf = BytesIO()
                Image.fromarray(cv2.cvtColor(terbaik[2], cv2.COLOR_BGR2RGB)).save(buf, "JPEG", quality=90)
                hasil.append((terbaik[1] / fps, buf.getvalue()))
    finally:
        cap.release()
        os.remove(path)
    if not hasil:
        raise VideoGagal("Tidak ada frame yang bisa diambil dari video ini.")
    return hasil


def _median_kategori(nilai: list[str], opsi: list[str]) -> str:
    urut = sorted(opsi.index(v) if v in opsi else 0 for v in nilai)
    return opsi[urut[len(urut) // 2]]


def gabung_hasil(hasil: list[HasilAnalisis]) -> Optional[HasilAnalisis]:
    """Satukan hasil beberapa frame. Frame yang bukan jalan diabaikan.

    - luas retak: rata-rata antar-frame
    - lebar retak & alur roda: median kategori
    - jumlah lubang: terbanyak dalam satu frame (frame saling tumpang tindih, jadi tidak dijumlahkan)
    """
    jalan = [h for h in hasil if h.jalan_terlihat]
    if not jalan:
        return None
    terburuk = max(jalan, key=lambda h: (h.jumlah_lubang, h.luas_retak_persen))
    return HasilAnalisis(
        jalan_terlihat=True,
        jenis_perkerasan=Counter(h.jenis_perkerasan for h in jalan).most_common(1)[0][0],
        deskripsi=f"Gabungan {len(jalan)} frame video. {terburuk.deskripsi}",
        kerusakan=[k for h in jalan for k in h.kerusakan],
        luas_retak_persen=statistics.fmean(h.luas_retak_persen for h in jalan),
        lebar_retak=_median_kategori([h.lebar_retak for h in jalan], LEBAR_OPSI),
        jumlah_lubang=max(h.jumlah_lubang for h in jalan),
        kedalaman_alur=_median_kategori([h.kedalaman_alur for h in jalan], ALUR_OPSI),
        keyakinan=statistics.fmean(h.keyakinan for h in jalan),
        rekomendasi=terburuk.rekomendasi,
    )
