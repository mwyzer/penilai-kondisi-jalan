import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import analisis_deepseek as ad  # noqa: E402
from analisis import AnalisisGagal, HasilAnalisis  # noqa: E402

JSON_OK = HasilAnalisis(
    jalan_terlihat=True, jenis_perkerasan="aspal", deskripsi="Jalan aspal.", kerusakan=[],
    luas_retak_persen=5, lebar_retak="tidak ada", jumlah_lubang=0, kedalaman_alur="tidak ada",
    keyakinan=0.7, rekomendasi="Pemeliharaan rutin.").model_dump_json()


def _foto() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (640, 480), "gray").save(buf, "JPEG")
    return buf.getvalue()


class _FakeOpenAI:
    def __init__(self, content=None, finish="stop", error=None):
        self.kwargs = None
        self._content, self._finish, self._error = content, finish, error
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.kwargs = kwargs
        if self._error:
            raise self._error
        msg = SimpleNamespace(content=self._content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason=self._finish)])


def _pakai(monkeypatch, fake):
    monkeypatch.setattr(ad.openai, "OpenAI", lambda **kw: fake)


def test_permintaan_berisi_gambar_dan_json_mode(monkeypatch):
    fake = _FakeOpenAI(JSON_OK)
    _pakai(monkeypatch, fake)
    h = ad.analisis_deepseek(_foto(), "Konteks: uji", "sk-test")
    assert h.keyakinan == 0.7
    kw = fake.kwargs
    assert kw["model"] == "deepseek-flash" and kw["response_format"] == {"type": "json_object"}
    img, txt = kw["messages"][1]["content"]
    assert img["image_url"]["url"].startswith("data:image/jpeg;base64,") and txt["text"] == "Konteks: uji"


def test_tanpa_key():
    with pytest.raises(AnalisisGagal, match="DEEPSEEK_API_KEY"):
        ad.analisis_deepseek(_foto(), "x", None)


def test_json_rusak(monkeypatch):
    _pakai(monkeypatch, _FakeOpenAI("bukan json"))
    with pytest.raises(AnalisisGagal, match="tidak terbaca"):
        ad.analisis_deepseek(_foto(), "x", "sk-test")


def test_terpotong(monkeypatch):
    _pakai(monkeypatch, _FakeOpenAI(JSON_OK, finish="length"))
    with pytest.raises(AnalisisGagal, match="tidak lengkap"):
        ad.analisis_deepseek(_foto(), "x", "sk-test")
