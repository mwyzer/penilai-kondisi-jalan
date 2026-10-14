"""Penilai Kondisi Jalan — versi Streamlit (penilaian manual atau dibantu AI, SDI dihitung otomatis)."""
import json
from datetime import date
from html import escape

import pandas as pd
import pydeck as pdk
import streamlit as st

from ai import analisis_ai, nama_penyedia
from analisis import WARNA_JENIS, AnalisisGagal, gambar_kotak, nilai_lembar
from exif_gps import baca_gps, maps_link
from sdi import ALUR_OPSI, KELAS, LEBAR_OPSI, compute_sdi, fmt_sdi, kelas_dari_label
from statistik import MIN_N_RUAS, pemulusan_gaussian, segmen_aneh, statistik_ruas
from storage import EXAMPLE_LOG, load_log, save_log, to_csv, to_geojson
from ui_lain import tampil_banyak_foto, tampil_impor, tampil_sensor
from video import VideoGagal, ambil_frame, gabung_hasil

st.set_page_config(page_title="Penilai Kondisi Jalan", page_icon="🛣️", layout="wide")

MODE_FOTO, MODE_VIDEO = "Single photo", "Short video"
MODE_BANYAK, MODE_IMPOR, MODE_SENSOR = "Multiple photos", "Import CSV/GeoJSON", "Vibration sensor"

DEFAULTS = {"ruas": "Jl. Contoh Raya", "sta": "2+100", "panjang": 20, "lat": "-6.915110", "lon": "107.610640",
            "retak": 12, "lebar": "1-3 mm", "lubang": 2, "alur": "tidak ada", "waktu_foto": "", "gps_info": None,
            "analisis": None, "analisis_err": None, "video_frames": None, "jumlah_frame": 5}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)


def hex_rgb(h: str) -> list[int]:
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def baca_koordinat():
    try:
        lat = float(str(st.session_state.lat).replace(",", "."))
        lon = float(str(st.session_state.lon).replace(",", "."))
    except ValueError:
        return None
    return (lat, lon) if abs(lat) <= 90 and abs(lon) <= 180 else None


def konteks_segmen(sumber: str) -> str:
    return (f"Konteks: ruas \"{st.session_state.ruas}\", STA {st.session_state.sta}, "
            f"{sumber} mewakili ±{st.session_state.panjang} m jalan.")


def bersihkan_analisis():
    st.session_state.analisis = st.session_state.analisis_err = st.session_state.video_frames = None


def jalankan_analisis():
    f = st.session_state.get("foto")
    if f is None:
        return
    st.session_state.analisis_err = None
    try:
        with st.spinner(f"{nama_penyedia()} sedang memeriksa foto… biasanya 10–60 detik."):
            h = analisis_ai(f.getvalue(), konteks_segmen("foto"))
    except AnalisisGagal as e:
        st.session_state.analisis_err = str(e)
        return
    st.session_state.analisis = h
    if h.jalan_terlihat:
        st.session_state.update(nilai_lembar(h))
    else:
        st.session_state.analisis_err = ("Foto ini tampaknya bukan permukaan jalan. "
                                         "Coba foto lain yang memperlihatkan perkerasan.")


def jalankan_video():
    f = st.session_state.get("video")
    if f is None:
        return
    bersihkan_analisis()
    try:
        with st.spinner("Mengambil frame paling tajam dari video…"):
            frames = ambil_frame(f.getvalue(), st.session_state.jumlah_frame, f.name)
    except VideoGagal as e:
        st.session_state.analisis_err = str(e)
        return
    hasil = []
    with st.spinner(f"{nama_penyedia()} sedang memeriksa {len(frames)} frame… bisa beberapa menit."):
        for detik, data in frames:
            try:
                hasil.append((detik, data, analisis_ai(data, konteks_segmen("video") + f" Frame detik ke-{detik:.1f}."), None))
            except AnalisisGagal as e:
                hasil.append((detik, data, None, str(e)))
    st.session_state.video_frames = hasil
    gabungan = gabung_hasil([h for _, _, h, _ in hasil if h])
    if gabungan is None:
        galat = next((e for _, _, _, e in hasil if e), None)
        st.session_state.analisis_err = galat or "Tidak ada frame yang memperlihatkan permukaan jalan."
        return
    st.session_state.analisis = gabungan
    st.session_state.update(nilai_lembar(gabungan))


def foto_berubah():
    bersihkan_analisis()
    f = st.session_state.get("foto")
    if f is None:
        st.session_state.gps_info = None
        return
    gps = baca_gps(f.getvalue())
    st.session_state.waktu_foto = gps.get("waktu", "")
    if "lat" in gps:
        st.session_state.lat, st.session_state.lon = f"{gps['lat']:.6f}", f"{gps['lon']:.6f}"
    else:
        st.session_state.lat = st.session_state.lon = ""
    st.session_state.gps_info = gps


def mode_berubah():
    bersihkan_analisis()
    st.session_state.gps_info = None
    st.session_state.waktu_foto = ""


def tampil_temuan(h):
    st.markdown(f"**Kerusakan terdeteksi** · perkerasan: {h.jenis_perkerasan}")
    st.write(h.deskripsi)
    for k in h.kerusakan:
        warna = WARNA_JENIS.get(k.jenis, WARNA_JENIS["lainnya"])
        st.markdown(f"<span style='color:{warna}'>●</span> **{escape(k.jenis)}** · {k.tingkat}"
                    f"{' — ' + escape(k.catatan) if k.catatan else ''}", unsafe_allow_html=True)
    if not h.kerusakan:
        st.caption("Tidak ada kerusakan yang terlihat.")
    yakin = min(1.0, max(0.0, h.keyakinan))
    st.progress(yakin, text=f"Keyakinan AI {round(yakin * 100)}%")


# ---------- Header ----------
st.caption("SURVEI KONDISI PERKERASAN · METODE SDI BINA MARGA")
st.title("Penilai Kondisi Jalan")
st.write("Pilih sumber data, lalu isi kerusakan secara manual atau minta AI mengisinya. Nilai Surface Distress Index "
         "(SDI) dihitung otomatis dan semua angka bisa dikoreksi surveyor.")
mode = st.radio("Sumber data", [MODE_FOTO, MODE_VIDEO, MODE_BANYAK, MODE_IMPOR, MODE_SENSOR],
                horizontal=True, key="mode", on_change=mode_berubah)

if mode == MODE_BANYAK:
    tampil_banyak_foto()
elif mode == MODE_IMPOR:
    tampil_impor()
elif mode == MODE_SENSOR:
    tampil_sensor()
else:
    kiri, kanan = st.columns(2, gap="large")

    # ---------- Kiri: identitas segmen + foto/video ----------
    with kiri:
        if mode == MODE_FOTO:
            st.subheader("Foto & identitas segmen")
            st.file_uploader("Foto jalan (JPG, PNG, WebP)", type=["jpg", "jpeg", "png", "webp"],
                             key="foto", on_change=foto_berubah)
        else:
            st.subheader("Video & identitas segmen")
            st.file_uploader("Video jalan pendek (MP4, MOV, AVI, WebM)", type=["mp4", "mov", "avi", "mkv", "webm"],
                             key="video", on_change=bersihkan_analisis)
            st.slider("Jumlah frame yang dianalisis", 3, 10, key="jumlah_frame",
                      help="Video dibagi rata; dari tiap bagian diambil frame paling tajam. Satu frame = satu panggilan AI.")
        c1, c2, c3 = st.columns(3)
        c1.text_input("Nama ruas", key="ruas")
        c2.text_input("STA (km+m)", key="sta")
        c3.number_input("Panjang terwakili (m)", min_value=1, step=1, key="panjang",
                        help="Untuk video: panjang jalan yang dilalui selama rekaman.")
        c4, c5 = st.columns(2)
        c4.text_input("Lintang (lat)", key="lat", placeholder="-6.91511")
        c5.text_input("Bujur (lon)", key="lon", placeholder="107.61064")

        gps, koord = st.session_state.gps_info, baca_koordinat()
        if gps and "lat" in gps and koord:
            extra = (f" · diambil {gps['waktu']}" if gps.get("waktu") else "") + \
                    (f" · arah {round(gps['arah'])}°" if gps.get("arah") is not None else "")
            st.success(f"GPS dari foto: **{koord[0]:.6f}, {koord[1]:.6f}**{extra} · [lihat di peta ↗]({maps_link(*koord)})")
        elif gps and "alasan" in gps and not koord:
            st.warning("Tidak ada GPS. " + gps["alasan"])
        elif koord:
            st.info(f"Lokasi: **{koord[0]:.6f}, {koord[1]:.6f}** · [lihat di peta ↗]({maps_link(*koord)})")
        else:
            st.warning("Belum ada koordinat. Isi lintang/bujur secara manual (format desimal, mis. -6.91511)"
                       + (" atau unggah foto JPEG ber-GPS." if mode == MODE_FOTO else "."))

        h = st.session_state.analisis
        if mode == MODE_FOTO:
            foto = st.session_state.foto
            st.button("Analisis foto otomatis", type="primary", on_click=jalankan_analisis, disabled=foto is None,
                      help=f"{nama_penyedia()} membaca foto dan mengisi lembar hitung SDI. Angkanya tetap bisa dikoreksi."
                      if foto is not None else "Unggah foto jalan dulu.")
            if st.session_state.analisis_err:
                st.error(st.session_state.analisis_err)
            if foto is not None:
                if h and h.kerusakan:
                    st.image(gambar_kotak(foto.getvalue(), h), caption="Kerusakan terdeteksi", width="stretch")
                else:
                    st.image(foto, caption="Foto permukaan jalan", width="stretch")
            if h:
                tampil_temuan(h)
        else:
            video = st.session_state.get("video")
            n = st.session_state.jumlah_frame
            st.button(f"Analisis video otomatis · {n} panggilan AI", type="primary", on_click=jalankan_video,
                      disabled=video is None, help=None if video is not None else "Unggah video jalan dulu.")
            if st.session_state.analisis_err:
                st.error(st.session_state.analisis_err)
            frames = st.session_state.video_frames
            if frames:
                kolom = st.columns(min(3, len(frames)))
                for i, (detik, data, hf, galat) in enumerate(frames):
                    with kolom[i % len(kolom)]:
                        gambar = gambar_kotak(data, hf) if hf and hf.kerusakan else data
                        ket = (f"detik {detik:.1f} · gagal" if galat else f"detik {detik:.1f} · bukan jalan"
                               if not hf.jalan_terlihat else
                               f"detik {detik:.1f} · retak {hf.luas_retak_persen:.0f}% · lubang {hf.jumlah_lubang}")
                        st.image(gambar, caption=ket, width="stretch")
            elif video is not None:
                st.video(video)
            if h:
                tampil_temuan(h)
                st.caption("Gabungan frame: luas retak = rata-rata, lebar retak & alur roda = median, "
                           "jumlah lubang = terbanyak dalam satu frame (agar lubang yang sama tidak terhitung dua kali).")
        if h:
            st.caption("Hasil AI adalah perkiraan visual. Periksa angka di lembar hitung dan koreksi bila perlu.")

    # ---------- Kanan: lembar hitung SDI ----------
    with kanan:
        st.subheader("Lembar hitung SDI")
        a, b = st.columns(2)
        a.number_input("Luas retak (% permukaan)", min_value=0, max_value=100, step=1, key="retak")
        b.selectbox("Lebar retak rata-rata", LEBAR_OPSI, key="lebar")
        a.number_input("Jumlah lubang", min_value=0, step=1, key="lubang")
        b.selectbox("Kedalaman alur roda", ALUR_OPSI, key="alur")

        s = compute_sdi(st.session_state.retak, st.session_state.lebar, st.session_state.lubang,
                        st.session_state.alur, st.session_state.panjang)
        k = s.kelas
        st.markdown(
            f"""<div style="background:{k.latar};color:{k.warna};border:2px solid {k.warna};border-radius:10px;
            padding:14px 18px;display:flex;gap:18px;align-items:center;margin:8px 0">
            <div style="font:700 2.6rem/1 monospace">{fmt_sdi(s.sdi)}</div>
            <div><div style="font-weight:700;font-size:1.25rem">{k.label}</div>
            <div style="color:#1c2124">{k.tindakan}</div></div></div>""",
            unsafe_allow_html=True)
        st.markdown(" ".join(
            f"<span style='display:inline-block;padding:3px 9px;margin:2px;border-radius:6px;font-size:.8rem;"
            f"border:1px solid {c.warna};{'background:' + c.warna + ';color:#fff;font-weight:600' if c is k else 'color:' + c.warna}'>"
            f"{c.label} {c.rentang}</span>" for c in KELAS), unsafe_allow_html=True)

        st.table(pd.DataFrame({
            "Langkah": ["SDI₁ (luas retak)", "SDI₂ (lebar retak)", "Tambahan lubang", "Tambahan alur roda", "SDI"],
            "Nilai": [fmt_sdi(s.sdi1), fmt_sdi(s.sdi2), "+" + fmt_sdi(s.add_l), "+" + fmt_sdi(s.add_a), fmt_sdi(s.sdi)],
        }).set_index("Langkah"))
        st.caption(f"Lubang dihitung per 100 m: {st.session_state.lubang} lubang di {st.session_state.panjang} m "
                   f"≈ {s.per100:.1f} per 100 m. Ubah “Panjang terwakili” sesuai jarak jalan yang tampak.")
        h = st.session_state.analisis
        saran = (h.rekomendasi + " ") if h and h.jalan_terlihat and h.rekomendasi else ""
        catatan = (f" Catatan: SDI dirancang untuk perkerasan aspal; untuk perkerasan {h.jenis_perkerasan} "
                   "gunakan hasil ini sebagai indikasi saja.") if h and h.jenis_perkerasan != "aspal" else ""
        st.markdown(f"**Rekomendasi penanganan:** {saran}Kategori SDI: {k.tindakan.lower()}.{catatan}")

        if st.button("Simpan ke daftar segmen", type="primary"):
            log = load_log()
            log.append({"ruas": st.session_state.ruas or "–", "sta": st.session_state.sta or "–",
                        "panjang": st.session_state.panjang, "retak": st.session_state.retak,
                        "per100": round(s.per100, 1), "sdi": s.sdi, "cls": k.label, "tgl": date.today().isoformat(),
                        "lat": koord[0] if koord else None, "lon": koord[1] if koord else None,
                        "waktu_foto": st.session_state.waktu_foto})
            save_log(log)
            st.toast(f"Segmen STA {st.session_state.sta} disimpan sebagai “{k.label}”"
                     + ("" if koord else " (tanpa koordinat, tidak tampil di peta)") + ".")

# ---------- Daftar segmen ----------
st.divider()
st.subheader("Daftar segmen")
log = load_log()
is_ex = not log
rows = log or EXAMPLE_LOG
if is_ex:
    st.caption("Belum ada segmen tersimpan, jadi yang ditampilkan di bawah adalah data contoh.")

total = sum(float(r["panjang"]) for r in rows)
for col, c in zip(st.columns(len(KELAS)), KELAS):
    m = sum(float(r["panjang"]) for r in rows if r["cls"] == c.label)
    col.metric(c.label, f"{m:g} m", f"{round(m * 100 / total) if total else 0}% dari {total:g} m", delta_color="off")

st.markdown("**Perbandingan antar-ruas**")
stat_ruas = statistik_ruas(rows)
st.dataframe(pd.DataFrame([{
    "Ruas": s["ruas"], "Segmen": s["n"], "Rata-rata SDI": round(s["rata"], 1), "Simpangan baku": round(s["sb"], 1),
    "Interval 95%": f"{s['ci_bawah']:.0f} – {s['ci_atas']:.0f}" if s["n"] > 1 else "–",
    "Catatan": "" if s["n"] >= MIN_N_RUAS else f"Kurang dari {MIN_N_RUAS} segmen, belum bermakna",
} for s in stat_ruas]), hide_index=True, width="stretch")
st.caption("Interval 95% adalah perkiraan rentang rata-rata SDI ruas. Bila dua ruas intervalnya tidak saling tumpang tindih, "
           "perbedaannya kemungkinan nyata. Hasilnya kasar bila jumlah segmen sedikit.")

halus = pemulusan_gaussian(rows)
aneh = segmen_aneh(rows)

titik = [r for r in rows if r.get("lat") is not None and r.get("lon") is not None]
if titik:
    df_map = pd.DataFrame([{**r, "warna": hex_rgb(kelas_dari_label(r["cls"]).warna)} for r in titik])
    st.pydeck_chart(pdk.Deck(
        initial_view_state=pdk.ViewState(latitude=df_map.lat.mean(), longitude=df_map.lon.mean(), zoom=16),
        layers=[pdk.Layer("ScatterplotLayer", df_map, get_position="[lon, lat]", get_fill_color="warna",
                          get_radius=6, radius_min_pixels=6, pickable=True)],
        tooltip={"text": "{ruas} STA {sta}\nSDI {sdi} · {cls}"},
    ))
else:
    st.info("Belum ada segmen berkoordinat. Simpan segmen dengan lintang/bujur agar titiknya muncul di peta.")

st.dataframe(pd.DataFrame([{
    "Ruas": r["ruas"], "STA": r["sta"], "Panjang (m)": r["panjang"], "Retak %": r["retak"],
    "Lubang/100 m": r["per100"], "SDI": r["sdi"], "SDI halus": None if halus[i] is None else round(halus[i], 1),
    "Aneh?": "ya" if aneh[i] else "", "Kondisi": r["cls"],
    "Lokasi": maps_link(r["lat"], r["lon"]) if r.get("lat") is not None else None, "Tanggal": r["tgl"],
} for i, r in enumerate(rows)]), hide_index=True, width="stretch",
    column_config={"Lokasi": st.column_config.LinkColumn("Lokasi", display_text="buka peta ↗")})

d1, d2, d3, d4 = st.columns([1, 1, 2, 1])
d1.download_button("Unduh CSV", to_csv(rows), "segmen.csv", "text/csv")
d2.download_button("Unduh GeoJSON", json.dumps(to_geojson(rows), ensure_ascii=False, indent=1),
                   "segmen.geojson", "application/geo+json")
if not is_ex:
    pilih = d3.selectbox("Hapus segmen", range(len(log)), label_visibility="collapsed",
                         format_func=lambda i: f"Hapus: {log[i]['ruas']} STA {log[i]['sta']}")
    if d3.button("Hapus baris terpilih"):
        log.pop(pilih)
        save_log(log)
        st.rerun()
    if d4.button("Kosongkan"):
        save_log([])
        st.rerun()
st.caption("Daftar disimpan di data/segmen.json. CSV untuk spreadsheet; GeoJSON untuk QGIS atau geojson.io.")
