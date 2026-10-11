# Penilai Kondisi Jalan (Python / Streamlit)

Penilaian kondisi perkerasan dengan metode SDI (Surface Distress Index) Bina Marga.
Surveyor mengisi kerusakan secara manual (luas & lebar retak, jumlah lubang, alur roda), SDI dan kelas kondisi dihitung otomatis.
Lokasi diambil dari GPS di EXIF foto JPEG bila ada.

## Menjalankan

```bash
pip install -r requirements.txt
streamlit run app.py
```

Buka http://localhost:8501.

## Analisis foto otomatis (opsional)

Tombol **Analisis foto otomatis** mengirim foto ke model AI, lalu mengisi lembar hitung SDI dan menandai kerusakan di foto.
Semua angka tetap bisa dikoreksi. Tanpa API key, aplikasi tetap bisa dipakai secara manual.

Ada dua penyedia AI; pilih lewat `AI_PROVIDER` di `.streamlit/secrets.toml`:

| `AI_PROVIDER` | Model | Kunci yang dibutuhkan | Daftar kunci |
|---|---|---|---|
| `deepseek` (default) | `deepseek-flash` | `DEEPSEEK_API_KEY` | https://platform.deepseek.com |
| `claude` | `claude-opus-5-5` | `ANTHROPIC_API_KEY` | https://console.anthropic.com |

Contoh `.streamlit/secrets.toml`:

```toml
AI_PROVIDER = "deepseek"
DEEPSEEK_API_KEY = "isi-kunci-deepseek"
# ANTHROPIC_API_KEY = "isi-kunci-claude"  # hanya bila AI_PROVIDER = "claude"
```

Jalankan ulang `streamlit run app.py` setelah mengubah berkas ini. Setiap analisis memakai kredit API (biayanya kecil per foto). Lebar retak dan kedalaman alur hanyalah perkiraan visual dari foto.

## Berkas

- `app.py` — antarmuka Streamlit
- `sdi.py` — rumus SDI dan kelas kondisi
- `analisis.py` — analisis foto dengan Claude (dan skema hasil AI bersama)
- `analisis_deepseek.py` — analisis foto dengan DeepSeek
- `exif_gps.py` — membaca GPS/waktu dari foto
- `storage.py` — daftar segmen (`data/segmen.json`), ekspor CSV & GeoJSON
- `tests/` — `pytest`
- `penilai-kondisi-jalan.html` — versi lama (HTML/JavaScript, dengan analisis AI lewat Claude Artifact)
