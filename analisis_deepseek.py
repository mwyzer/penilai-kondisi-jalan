"""Analisis foto jalan dengan DeepSeek (model deepseek-flash, menerima gambar)."""
import json
from typing import Optional

import openai
from pydantic import ValidationError

from analisis import SYSTEM, AnalisisGagal, HasilAnalisis, _jpeg_b64, siapkan_foto

MODEL = "deepseek-flash"
BASE_URL = "https://api.deepseek.com"


def _instruksi() -> str:
    skema = json.dumps(HasilAnalisis.model_json_schema(), ensure_ascii=False)
    return (f"{SYSTEM}\n\nBalas HANYA dengan satu objek JSON yang valid sesuai skema berikut:\n{skema}")


def analisis_deepseek(data: bytes, konteks: str, api_key: Optional[str]) -> HasilAnalisis:
    if not api_key:
        raise AnalisisGagal("DEEPSEEK_API_KEY belum diatur. Isi di .streamlit/secrets.toml (lihat README).")
    img = siapkan_foto(data)
    client = openai.OpenAI(api_key=api_key, base_url=BASE_URL, max_retries=2, timeout=120)
    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=8000,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _instruksi()},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_jpeg_b64(img)}"}},
                    {"type": "text", "text": konteks},
                ]},
            ],
        )
    except openai.AuthenticationError:
        raise AnalisisGagal("API key DeepSeek tidak valid. Periksa DEEPSEEK_API_KEY.")
    except openai.RateLimitError:
        raise AnalisisGagal("Terlalu banyak permintaan. Tunggu sebentar, lalu coba lagi.")
    except openai.BadRequestError as e:
        raise AnalisisGagal(f"Permintaan ditolak DeepSeek: {e.message}")
    except openai.APIConnectionError:
        raise AnalisisGagal("Tidak bisa terhubung ke DeepSeek. Periksa koneksi internet.")
    except openai.APIStatusError as e:
        raise AnalisisGagal(f"Layanan DeepSeek sedang bermasalah ({e.status_code}). Coba lagi nanti.")

    choice = response.choices[0]
    if choice.finish_reason == "length":
        raise AnalisisGagal("Jawaban AI tidak lengkap. Tekan tombol analisis sekali lagi.")
    try:
        return HasilAnalisis.model_validate_json(choice.message.content or "")
    except (ValidationError, ValueError):
        raise AnalisisGagal("Jawaban AI tidak terbaca. Tekan “Analisis foto otomatis” sekali lagi.")
