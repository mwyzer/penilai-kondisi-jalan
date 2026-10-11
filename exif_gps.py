"""Membaca lokasi GPS dan waktu pengambilan dari EXIF foto JPEG."""
from io import BytesIO

from PIL import Image

GPS_IFD = 0x8825
EXIF_IFD = 0x8769
DATETIME_ORIGINAL = 0x9003

ALASAN_BUKAN_JPEG = "Lokasi hanya bisa dibaca dari foto JPEG."
ALASAN_TANPA_GPS = (
    "Foto ini tidak menyimpan lokasi. Penyebab umum: tag lokasi kamera mati, foto dikirim lewat "
    "WhatsApp/Telegram/media sosial, atau peramban HP menghapusnya saat unggah. "
    "Unggah berkas asli dari laptop, atau isi koordinat manual."
)


def _dms(nilai) -> float:
    d, m, s = (float(x) for x in nilai)
    return d + m / 60 + s / 3600


def baca_gps(data: bytes) -> dict:
    """Kembalikan {lat, lon, waktu, arah} (yang tersedia) atau {"alasan": ...} bila tidak ada GPS."""
    try:
        img = Image.open(BytesIO(data))
    except Exception:
        return {"alasan": ALASAN_BUKAN_JPEG}
    if img.format != "JPEG":
        return {"alasan": ALASAN_BUKAN_JPEG}

    out: dict = {}
    try:
        exif = img.getexif()
        waktu = exif.get_ifd(EXIF_IFD).get(DATETIME_ORIGINAL)
        if waktu:
            out["waktu"] = str(waktu).strip()
        g = exif.get_ifd(GPS_IFD)
        if 2 in g and 4 in g:
            lat, lon = _dms(g[2]), _dms(g[4])
            if str(g.get(1, "")).strip() == "S":
                lat = -lat
            if str(g.get(3, "")).strip() == "W":
                lon = -lon
            if not (lat == 0 and lon == 0) and abs(lat) <= 90 and abs(lon) <= 180:
                out["lat"], out["lon"] = lat, lon
        if 0x11 in g:
            out["arah"] = float(g[0x11])
    except Exception:
        pass  # EXIF rusak: kembalikan yang sudah terbaca

    if "lat" not in out:
        out["alasan"] = ALASAN_TANPA_GPS
    return out


def maps_link(lat: float, lon: float) -> str:
    return f"https://www.google.com/maps?q={lat:.6f},{lon:.6f}"
