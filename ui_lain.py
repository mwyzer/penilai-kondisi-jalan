"""Tampilan opsi input: beberapa foto sekaligus, impor CSV/GeoJSON, dan sensor getaran."""
from datetime import date

import pandas as pd
import pydeck as pdk
import streamlit as st

from ai import analisis_ai, nama_penyedia
from analisis import AnalisisGagal, nilai_lembar
from exif_gps import baca_gps
from impor import KOLOM_WAJIB, dari_berkas
from sdi import ALUR_OPSI, LEBAR_OPSI, compute_sdi
from sensor import baca_csv, kekasaran_per_segmen, tebak_kolom
from statistik import meter_ke_sta, sta_ke_meter
from storage import load_log, save_log

TIDAK_ADA = "– tidak ada –"


def _tambah_ke_log(baru: list[dict]) -> None:
    log = load_log()
    log.extend(baru)
    save_log(log)


# ---------- Beberapa foto sekaligus ----------
def tampil_banyak_foto() -> None:
    st.subheader("Beberapa foto sekaligus")
    st.caption("Satu foto mewakili satu segmen. STA dihitung berurutan dari STA foto pertama dengan jarak tetap "
               "antar-foto. Lokasi diambil dari GPS foto bila ada.")
    c1, c2, c3 = st.columns(3)
    ruas = c1.text_input("Nama ruas", value=st.session_state.get("ruas", ""), key="b_ruas")
    sta0 = c2.text_input("STA foto pertama (km+m)", value="0+000", key="b_sta")
    jarak = c3.number_input("Jarak antar-foto (m)", min_value=1, value=20, step=1, key="b_jarak")
    berkas = st.file_uploader("Foto jalan (urutkan nama berkas sesuai arah survei)",
                              type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True, key="b_foto")
    pakai_ai = st.toggle(f"Isi otomatis dengan AI ({nama_penyedia()})", value=True, key="b_ai",
                         help="Matikan untuk mengisi semua angka secara manual di tabel.")
    m0 = sta_ke_meter(sta0)
    if m0 is None:
        st.error("Format STA tidak dikenali. Gunakan km+m, misalnya 0+000 atau 2+100.")
        return

    if berkas:
        berkas = sorted(berkas, key=lambda f: f.name)
        st.markdown("**Preview foto**")
        idx_key = "b_foto_idx"
        st.session_state.setdefault(idx_key, 0)
        idx = st.session_state[idx_key]
        idx = max(0, min(idx, len(berkas) - 1))
        st.session_state[idx_key] = idx

        col_prev, col_img, col_next = st.columns([1, 3, 1])
        with col_prev:
            if st.button("◀ Sebelumnya", key="b_prev", use_container_width=True):
                st.session_state[idx_key] = max(0, idx - 1)
                st.rerun()
        with col_img:
            st.image(berkas[idx], caption=f"{berkas[idx].name} · {idx+1}/{len(berkas)}", use_container_width=True)
        with col_next:
            if st.button("Selanjutnya ▶", key="b_next", use_container_width=True):
                st.session_state[idx_key] = min(len(berkas) - 1, idx + 1)
                st.rerun()
        st.divider()

    if berkas:
        biaya = f" · {len(berkas)} panggilan AI" if pakai_ai else ""
        if st.button(f"Proses {len(berkas)} foto{biaya}", type="primary"):
            baris, bar = [], st.progress(0.0)
            for i, f in enumerate(berkas):
                data, sta = f.getvalue(), meter_ke_sta(m0 + i * jarak)
                gps = baca_gps(data)
                r = {"Foto": f.name, "STA": sta, "Retak %": 0, "Lebar retak": "tidak ada", "Lubang": 0,
                     "Alur roda": "tidak ada", "Lat": gps.get("lat"), "Lon": gps.get("lon"),
                     "Waktu foto": gps.get("waktu", ""), "Catatan": ""}
                if pakai_ai:
                    bar.progress(i / len(berkas), text=f"Menganalisis {f.name} ({i + 1}/{len(berkas)})…")
                    try:
                        h = analisis_ai(data, f"Konteks: ruas \"{ruas}\", STA {sta}, foto mewakili ±{jarak} m jalan.")
                        if h.jalan_terlihat:
                            v = nilai_lembar(h)
                            r.update({"Retak %": v["retak"], "Lebar retak": v["lebar"], "Lubang": v["lubang"],
                                      "Alur roda": v["alur"], "Catatan": h.deskripsi})
                        else:
                            r["Catatan"] = "Bukan foto jalan menurut AI"
                    except AnalisisGagal as e:
                        r["Catatan"] = f"Gagal: {e}"
                baris.append(r)
            bar.progress(1.0, text="Selesai")
            st.session_state.batch_df = pd.DataFrame(baris)

    df = st.session_state.get("batch_df")
    if df is None:
        return
    st.markdown("**Periksa dan koreksi sebelum disimpan**")
    edit = st.data_editor(df, key="b_editor", hide_index=True, width="stretch", disabled=["Foto"], column_config={
        "Retak %": st.column_config.NumberColumn(min_value=0, max_value=100, step=1),
        "Lebar retak": st.column_config.SelectboxColumn(options=LEBAR_OPSI, required=True),
        "Lubang": st.column_config.NumberColumn(min_value=0, step=1),
        "Alur roda": st.column_config.SelectboxColumn(options=ALUR_OPSI, required=True),
        "Lat": st.column_config.NumberColumn(format="%.6f"), "Lon": st.column_config.NumberColumn(format="%.6f"),
    })
    segmen = []
    for _, r in edit.iterrows():
        s = compute_sdi(r["Retak %"], r["Lebar retak"], r["Lubang"], r["Alur roda"], jarak)
        lat = None if pd.isna(r["Lat"]) else float(r["Lat"])
        lon = None if pd.isna(r["Lon"]) else float(r["Lon"])
        segmen.append({"ruas": ruas or "–", "sta": r["STA"], "panjang": jarak,
                       "retak": int(r["Retak %"] or 0), "per100": round(s.per100, 1), "sdi": s.sdi,
                       "cls": s.kelas.label, "tgl": date.today().isoformat(),
                       "lat": lat if lon is not None else None, "lon": lon if lat is not None else None,
                       "waktu_foto": r.get("Waktu foto") or ""})
    st.dataframe(pd.DataFrame([{"STA": x["sta"], "SDI": x["sdi"], "Kondisi": x["cls"]} for x in segmen]),
                 hide_index=True, width="stretch")
    if st.button(f"Simpan {len(segmen)} segmen ke daftar", type="primary", key="b_simpan"):
        _tambah_ke_log(segmen)
        st.session_state.batch_df = None
        st.toast(f"{len(segmen)} segmen disimpan.")
        st.rerun()


# ---------- Impor CSV / GeoJSON ----------
def tampil_impor() -> None:
    st.subheader("Impor CSV / GeoJSON")
    st.caption(f"Format sama dengan hasil “Unduh CSV/GeoJSON” aplikasi ini. Kolom wajib: {', '.join(KOLOM_WAJIB)}. "
               "Kolom lain (panjang_m, retak_persen, lubang_per_100m, lat, lon, tanggal) opsional. "
               "Kondisi dihitung ulang dari nilai SDI.")
    f = st.file_uploader("Berkas CSV atau GeoJSON", type=["csv", "geojson", "json"], key="i_berkas")
    if f is None:
        return
    rows, galat = dari_berkas(f.name, f.getvalue())
    if galat:
        st.warning(f"{len(galat)} baris dilewati:\n\n" + "\n".join(f"- {g}" for g in galat[:10])
                   + ("\n- …" if len(galat) > 10 else ""))
    if not rows:
        st.error("Tidak ada segmen yang bisa diimpor dari berkas ini.")
        return
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if st.button(f"Tambahkan {len(rows)} segmen ke daftar", type="primary", key="i_simpan"):
        _tambah_ke_log(rows)
        st.toast(f"{len(rows)} segmen diimpor.")


# ---------- Sensor getaran ----------
def tampil_sensor() -> None:
    st.subheader("Sensor getaran (akselerometer HP)")
    st.caption("Rekam dengan aplikasi seperti phyphox atau Physics Toolbox saat HP terpasang kokoh di kendaraan, "
               "lalu ekspor CSV. Aplikasi menghitung kekasaran per segmen dari getaran vertikal.")
    f = st.file_uploader("CSV akselerometer", type=["csv", "txt"], key="s_berkas")
    if f is None:
        return
    try:
        df = baca_csv(f.getvalue())
    except Exception as e:
        st.error(f"CSV tidak bisa dibaca: {e}")
        return
    kolom = list(df.columns)
    if len(kolom) < 2:
        st.error("CSV perlu minimal kolom waktu dan percepatan.")
        return
    tebak = tebak_kolom(kolom)

    def idx(nama, opsi):
        return opsi.index(nama) if nama in opsi else 0

    c1, c2, c3, c4 = st.columns(4)
    kol_waktu = c1.selectbox("Kolom waktu (detik)", kolom, index=idx(tebak["waktu"], kolom))
    kol_az = c2.selectbox("Kolom percepatan vertikal", kolom, index=idx(tebak["az"], kolom),
                          help="Sumbu yang tegak lurus permukaan jalan; biasanya z bila HP berbaring datar.")
    opsi_gps = [TIDAK_ADA] + kolom
    kol_lat = c3.selectbox("Kolom lintang (opsional)", opsi_gps, index=idx(tebak["lat"], opsi_gps))
    kol_lon = c4.selectbox("Kolom bujur (opsional)", opsi_gps, index=idx(tebak["lon"], opsi_gps))
    pakai_gps = kol_lat != TIDAK_ADA and kol_lon != TIDAK_ADA

    c5, c6, c7, c8 = st.columns(4)
    ruas = c5.text_input("Nama ruas", value=st.session_state.get("ruas", ""), key="s_ruas")
    sta0 = c6.text_input("STA awal rekaman", value="0+000", key="s_sta")
    panjang = c7.number_input("Panjang segmen (m)", min_value=10, value=100, step=10, key="s_panjang")
    kecepatan = c8.number_input("Kecepatan rata-rata (km/jam)", min_value=1, value=30, step=5, key="s_kec",
                                disabled=pakai_gps, help="Dipakai bila tidak ada kolom GPS.")
    m0 = sta_ke_meter(sta0)
    if m0 is None:
        st.error("Format STA tidak dikenali. Gunakan km+m, misalnya 0+000.")
        return
    try:
        hasil = kekasaran_per_segmen(df, kol_waktu, kol_az, panjang, None if pakai_gps else kecepatan,
                                     kol_lat if pakai_gps else None, kol_lon if pakai_gps else None, m0)
    except (ValueError, KeyError) as e:
        st.error(str(e))
        return
    if not hasil:
        st.warning("Rekaman terlalu pendek: tidak ada segmen dengan data yang cukup.")
        return

    tabel = pd.DataFrame([{"Ruas": ruas, "STA": r["sta"], "Sampel": r["sampel"], "RMS (m/s²)": round(r["rms"], 3),
                           "Puncak (m/s²)": round(r["puncak"], 2), "Relatif ke median": round(r["relatif"], 2),
                           **({"Lat": r["lat"], "Lon": r["lon"]} if pakai_gps else {})} for r in hasil])
    st.markdown(f"**{len(hasil)} segmen** · median RMS {pd.Series([r['rms'] for r in hasil]).median():.3f} m/s²")
    st.line_chart(tabel.set_index("STA")["RMS (m/s²)"], height=220)
    if pakai_gps:
        peta = tabel.rename(columns={"Lat": "lat", "Lon": "lon"})
        peta["warna"] = [[179, 38, 30] if v >= 1.5 else [195, 86, 27] if v >= 1.2 else [47, 125, 70]
                         for v in peta["Relatif ke median"]]
        st.pydeck_chart(pdk.Deck(
            initial_view_state=pdk.ViewState(latitude=peta.lat.mean(), longitude=peta.lon.mean(), zoom=15),
            layers=[pdk.Layer("ScatterplotLayer", peta, get_position="[lon, lat]", get_fill_color="warna",
                              get_radius=6, radius_min_pixels=5, pickable=True)],
            tooltip={"text": "STA {STA}\nRMS {RMS (m/s²)} m/s²"}))
        st.caption("Warna peta: hijau < 1,2× median, oranye 1,2–1,5× median, merah ≥ 1,5× median.")
    st.dataframe(tabel, hide_index=True, width="stretch")
    st.download_button("Unduh hasil (CSV)", tabel.to_csv(index=False), "kekasaran.csv", "text/csv")
    st.info("RMS getaran adalah indikator kekasaran relatif, bukan nilai IRI resmi. Bandingkan hanya antar-rekaman "
            "dengan kendaraan, kecepatan, dan posisi HP yang sama.")
