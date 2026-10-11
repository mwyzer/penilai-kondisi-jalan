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

Tombol **Analisis foto otomatis** mengirim foto ke Claude (`claude-opus-5-5`), lalu mengisi lembar hitung SDI dan menandai kerusakan di foto.
Semua angka tetap bisa dikoreksi. Tanpa API key, aplikasi tetap bisa dipakai secara manual.

1. Buat API key di https://console.anthropic.com.
2. Atur key dengan salah satu cara berikut:
   - environment variable `ANTHROPIC_API_KEY`, atau
   - berkas `.streamlit/secrets.toml` berisi `ANTHROPIC_API_KEY = "sk-ant-..."` (jangan dibagikan atau di-commit).
3. Jalankan ulang `streamlit run app.py`.

Setiap analisis memakai kredit API (biayanya kecil per foto). Lebar retak dan kedalaman alur hanyalah perkiraan visual dari foto.

## Berkas

- `app.py` — antarmuka Streamlit
- `sdi.py` — rumus SDI dan kelas kondisi
- `analisis.py` — analisis foto dengan Claude
- `exif_gps.py` — membaca GPS/waktu dari foto
- `storage.py` — daftar segmen (`data/segmen.json`), ekspor CSV & GeoJSON
- `tests/` — `pytest`
- `penilai-kondisi-jalan.html` — versi lama (HTML/JavaScript, dengan analisis AI lewat Claude Artifact)
