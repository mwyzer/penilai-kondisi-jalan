import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import analisis  # noqa: E402
from analisis import AnalisisGagal, HasilAnalisis, analisis_claude, gambar_kotak, nilai_lembar  # noqa: E402

CONTOH = HasilAnalisis(
    jalan_terlihat=True, jenis_perkerasan="aspal", deskripsi="Jalan aspal berlubang.",
    kerusakan=[{"jenis": "lubang", "tingkat": "berat", "kotak": [0.6, 0.76, 0.18, 0.12], "catatan": "±1 m"},
               {"jenis": "retak buaya", "tingkat": "sedang", "kotak": [0.9, 0.9, 0.5, 0.5], "catatan": ""},
               {"jenis": "tambalan", "tingkat": "ringan", "kotak": [0.1], "catatan": "kotak rusak"}],
    luas_retak_persen=12.4, lebar_retak="1-3 mm", jumlah_lubang=2, kedalaman_alur="tidak ada",
    keyakinan=0.8, rekomendasi="Tambal lubang.")


def _foto(w=3000, h=2000, fmt="JPEG") -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), "gray").save(buf, fmt)
    return buf.getvalue()


class _FakeClient:
    def __init__(self, response=None, error=None):
        self.kwargs = None
        self._response, self._error = response, error
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kwargs):
        self.kwargs = kwargs
        if self._error:
            raise self._error
        return self._response


def _pakai(monkeypatch, client):
    monkeypatch.setattr(analisis.anthropic, "Anthropic", lambda **_: client)


def test_nilai_lembar_dibatasi():
    assert nilai_lembar(CONTOH) == {"retak": 12, "lebar": "1-3 mm", "lubang": 2, "alur": "tidak ada"}
    aneh = CONTOH.model_copy(update={"luas_retak_persen": 140, "jumlah_lubang": -3})
    assert nilai_lembar(aneh)["retak"] == 100 and nilai_lembar(aneh)["lubang"] == 0


def test_gambar_kotak_kecil_dan_aman():
    img = gambar_kotak(_foto(), CONTOH)  # kotak keluar batas & kotak rusak tidak boleh error
    assert max(img.size) == analisis.SISI_MAKS


def test_permintaan_berisi_foto_dan_skema(monkeypatch):
    client = _FakeClient(SimpleNamespace(stop_reason="end_turn", parsed_output=CONTOH))
    _pakai(monkeypatch, client)
    assert analisis_claude(_foto(fmt="PNG"), "Konteks: uji") is CONTOH
    kw = client.kwargs
    assert kw["model"] == "claude-opus-5-5" and kw["output_format"] is HasilAnalisis
    img_block, txt_block = kw["messages"][0]["content"]
    assert img_block["source"]["media_type"] == "image/jpeg" and txt_block["text"] == "Konteks: uji"


@pytest.mark.parametrize("resp", [SimpleNamespace(stop_reason="refusal", parsed_output=None),
                                  SimpleNamespace(stop_reason="max_tokens", parsed_output=None)])
def test_jawaban_tidak_terpakai(monkeypatch, resp):
    _pakai(monkeypatch, _FakeClient(resp))
    with pytest.raises(AnalisisGagal):
        analisis_claude(_foto(), "x")


def test_tanpa_api_key(monkeypatch):
    _pakai(monkeypatch, _FakeClient(error=TypeError("Could not resolve authentication method.")))
    with pytest.raises(AnalisisGagal, match="API key"):
        analisis_claude(_foto(), "x")
