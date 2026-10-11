"""Analisis foto jalan otomatis dengan Claude (vision + structured output)."""
import base64
from io import BytesIO
from typing import Literal, Optional

import anthropic
from PIL import Image, ImageDraw, ImageOps
from pydantic import BaseModel

from sdi import ALUR_OPSI, LEBAR_OPSI

MODEL = "claude-opus-5-5"
SISI_MAKS = 1568  # sisi terpanjang foto yang dikirim; lebih besar hanya menambah biaya

JenisKerusakan = Literal["lubang", "retak buaya", "retak memanjang", "retak melintang", "retak blok", "alur roda",
                         "amblas", "pelepasan butir", "tambalan", "keriting", "kegemukan aspal", "lainnya"]

WARNA_JENIS = {"lubang": "#d23a2a", "retak buaya": "#e07a10", "retak memanjang": "#d9a400", "retak melintang": "#d9a400",
               "retak blok": "#e07a10", "alur roda": "#7b4fd1", "amblas": "#7b4fd1", "pelepasan butir": "#2d8bb8",
               "tambalan": "#3f9a5a", "keriting": "#2d8bb8", "kegemukan aspal": "#555f63", "lainnya": "#555f63"}


class Kerusakan(BaseModel):
    jenis: JenisKerusakan
    tingkat: Literal["ringan", "sedang", "berat"]
    kotak: list[float]  # [x, y, lebar, tinggi], ternormalisasi 0-1 dari kiri-atas foto
    catatan: str


class HasilAnalisis(BaseModel):
    jalan_terlihat: bool
    jenis_perkerasan: Literal["aspal", "beton", "paving", "kerikil/tanah", "lainnya"]
    deskripsi: str
    kerusakan: list[Kerusakan]
    luas_retak_persen: float
    lebar_retak: Literal["tidak ada", "<1 mm", "1-3 mm", ">3 mm"]
    jumlah_lubang: int
    kedalaman_alur: Literal["tidak ada", "<1 cm", "1-3 cm", ">3 cm"]
    keyakinan: float
    rekomendasi: str


SYSTEM = """Anda adalah inspektur kondisi jalan yang berpengalaman dengan metode survei SDI (Surface Distress Index) Bina Marga.
Foto yang diberikan adalah permukaan jalan. Identifikasi kerusakan perkerasan yang terlihat.

Panduan isian:
- deskripsi: 1-2 kalimat bahasa Indonesia tentang kondisi umum.
- kerusakan: maksimal 12 item; "kotak" adalah [x, y, lebar, tinggi] dalam koordinat ternormalisasi 0-1 dari kiri-atas foto; "catatan" singkat.
- luas_retak_persen: perkiraan persentase (0-100) luas permukaan jalan yang tampak yang mengalami retak.
- jumlah_lubang: jumlah lubang yang tampak di foto.
- keyakinan: 0-1, seberapa yakin penilaian Anda dari foto ini.
- rekomendasi: 1-2 kalimat penanganan teknis, bahasa Indonesia.
Jika foto bukan jalan, isi jalan_terlihat false dan biarkan kerusakan kosong. Jangan mengarang kerusakan yang tidak terlihat;
lebar retak dan kedalaman alur adalah perkiraan visual, pilih kategori yang paling mungkin."""


class AnalisisGagal(Exception):
    pass


def siapkan_foto(data: bytes) -> Image.Image:
    img = ImageOps.exif_transpose(Image.open(BytesIO(data))).convert("RGB")
    img.thumbnail((SISI_MAKS, SISI_MAKS))
    return img


def _jpeg_b64(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, "JPEG", quality=88)
    return base64.standard_b64encode(buf.getvalue()).decode()


def analisis_foto(data: bytes, konteks: str, api_key: Optional[str] = None) -> HasilAnalisis:
    img = siapkan_foto(data)
    try:
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        response = client.beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium"},
            system=SYSTEM,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _jpeg_b64(img)}},
                {"type": "text", "text": konteks},
            ]}],
            output_format=HasilAnalisis,
        )
    except anthropic.AuthenticationError:
        raise AnalisisGagal("API key Claude tidak valid. Periksa ANTHROPIC_API_KEY.")
    except anthropic.PermissionDeniedError:
        raise AnalisisGagal("API key tidak punya izin memakai model ini.")
    except anthropic.RateLimitError:
        raise AnalisisGagal("Terlalu banyak permintaan. Tunggu sebentar, lalu coba lagi.")
    except anthropic.BadRequestError as e:
        raise AnalisisGagal(f"Permintaan ditolak oleh API: {e.message}")
    except anthropic.APIStatusError as e:
        raise AnalisisGagal(f"Layanan Claude sedang bermasalah ({e.status_code}). Coba lagi nanti.")
    except anthropic.APIConnectionError:
        raise AnalisisGagal("Tidak bisa terhubung ke Claude. Periksa koneksi internet.")
    except TypeError as e:  # kredensial tidak ditemukan sama sekali
        if "api_key" in str(e) or "auth" in str(e).lower():
            raise AnalisisGagal("API key Claude belum diatur. Isi ANTHROPIC_API_KEY (lihat README).")
        raise

    if response.stop_reason == "refusal":
        raise AnalisisGagal("Claude tidak dapat menganalisis foto ini. Coba foto lain.")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise AnalisisGagal("Jawaban AI tidak lengkap. Tekan tombol analisis sekali lagi.")
    return response.parsed_output


def nilai_lembar(h: HasilAnalisis) -> dict:
    """Ubah hasil AI jadi nilai lembar hitung SDI (dibatasi ke rentang yang sah)."""
    return {
        "retak": int(round(min(100, max(0, h.luas_retak_persen)))),
        "lebar": h.lebar_retak if h.lebar_retak in LEBAR_OPSI else "tidak ada",
        "lubang": max(0, int(h.jumlah_lubang)),
        "alur": h.kedalaman_alur if h.kedalaman_alur in ALUR_OPSI else "tidak ada",
    }


def gambar_kotak(data: bytes, h: HasilAnalisis) -> Image.Image:
    """Gambar kotak kerusakan di atas foto."""
    img = siapkan_foto(data)
    draw = ImageDraw.Draw(img)
    W, H = img.size
    tebal = max(2, W // 300)
    for k in h.kerusakan:
        if len(k.kotak) != 4:
            continue
        x, y, w, hh = (min(1.0, max(0.0, float(v))) for v in k.kotak)
        x0, y0 = x * W, y * H
        x1, y1 = min(W - 1, (x + w) * W), min(H - 1, (y + hh) * H)
        if x1 <= x0 or y1 <= y0:
            continue
        warna = WARNA_JENIS.get(k.jenis, WARNA_JENIS["lainnya"])
        draw.rectangle([x0, y0, x1, y1], outline=warna, width=tebal)
        tb = draw.textbbox((x0, y0), k.jenis)
        ty = y0 - (tb[3] - tb[1]) - 4 if y0 > 16 else y0
        draw.rectangle([x0, ty, x0 + (tb[2] - tb[0]) + 6, ty + (tb[3] - tb[1]) + 4], fill=warna)
        draw.text((x0 + 3, ty + 1), k.jenis, fill="white")
    return img
