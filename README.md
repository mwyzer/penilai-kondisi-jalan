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

## Sumber data

Pilih sumber data di bagian atas aplikasi:

| Sumber | Input | Hasil |
|---|---|---|
| **Foto tunggal** | Satu foto per segmen (GPS dibaca dari EXIF JPEG) | Lembar hitung SDI, isi manual atau dengan AI |
| **Video pendek** | Video MP4/MOV/AVI/WebM | Frame paling tajam diambil merata dari video, dianalisis AI, lalu digabung ke lembar hitung SDI: luas retak dirata-rata, lebar retak dan alur roda diambil median, lubang diambil jumlah terbanyak dalam satu frame |
| **Beberapa foto** | Banyak foto sekaligus, satu foto per segmen | STA berurutan dari STA awal + jarak antar-foto; hasil bisa dikoreksi di tabel sebelum disimpan |
| **Impor CSV/GeoJSON** | Berkas dengan format sama seperti hasil ekspor (kolom wajib: `ruas`, `sta`, `sdi`) | Segmen ditambahkan ke daftar; kondisi dihitung ulang dari SDI |
| **Sensor getaran** | CSV akselerometer HP (misalnya phyphox atau Physics Toolbox) | RMS getaran vertikal per segmen, grafik, peta (bila ada GPS), dan unduhan CSV |

RMS getaran adalah indikator kekasaran **relatif**, bukan nilai IRI resmi. Bandingkan hanya antar-rekaman dengan kendaraan, kecepatan, dan posisi HP yang sama.

Daftar segmen menampilkan perbandingan antar-ruas (rata-rata, simpangan baku, interval 95%), SDI yang dihaluskan dengan kernel Gaussian sepanjang STA, dan penanda segmen yang nilainya menyimpang (|z| > 2).

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
- `ai.py` — memilih penyedia AI dari pengaturan
- `ui_lain.py` — tampilan opsi beberapa foto, impor, dan sensor getaran
- `video.py` — mengambil frame tajam dari video dan menggabungkan hasil analisis
- `impor.py` — membaca CSV/GeoJSON segmen
- `sensor.py` — menghitung kekasaran dari data akselerometer
- `statistik.py` — statistik per ruas, pemulusan Gaussian, deteksi segmen menyimpang
- `exif_gps.py` — membaca GPS/waktu dari foto
- `storage.py` — daftar segmen (`data/segmen.json`), ekspor CSV & GeoJSON
- `tests/` — `pytest`
- `penilai-kondisi-jalan.html` — versi lama (HTML/JavaScript, dengan analisis AI lewat Claude Artifact)
