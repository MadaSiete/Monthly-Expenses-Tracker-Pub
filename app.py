import pandas as pd
import streamlit as st
import cv2
import pytesseract
import numpy as np
import re
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

st.set_page_config(page_title="Expenses Tracker Service", page_icon="💸", layout="centered")

hide_pull_to_refresh = """
    <style>
    html, body, .stApp {
        overscroll-behavior: none !important;
    }
    </style>
"""
st.markdown(hide_pull_to_refresh, unsafe_allow_html=True)

if 'username' not in st.session_state:
    st.session_state.username = None

# --- HALAMAN LOGIN ---
if st.session_state.username is None:
    st.title("👋 Welcome to Tracker Keuangan")
    st.write("Silahkan Login!")
    
    with st.form("login_form"):
        username_input = st.text_input("Masukkan Username (Tanpa spasi):")
        submit_login = st.form_submit_button("Masuk Aplikasi")
        
        if submit_login:
            if username_input.strip() == "":
                st.warning("Mohon diisi")
            else:
                st.session_state.username = username_input.strip().lower()
                st.rerun()
    st.stop()

# --- MAIN APP ---
col_title, col_logout = st.columns([3, 1])
with col_title:
    st.title("💸 Tracker Keuangan")
with col_logout:
    if st.button("🚪 Keluar"):
        st.session_state.username = None
        st.rerun()
st.caption(f"👤 Akun aktif: **{st.session_state.username}**")

@st.cache_resource
def init_connection():
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

gc = init_connection()

# Nama File Master yang lu bikin manual di Drive (pakai storage 5TB lu)
MASTER_SHEET_NAME = "Tracker Master SaaS"

with st.spinner(f"Membuka database untuk {st.session_state.username}..."):
    try:
        sh = gc.open(MASTER_SHEET_NAME)
    except gspread.exceptions.SpreadsheetNotFound:
        # st.error(f"❌ File '{MASTER_SHEET_NAME}' belum ada atau lu belum nge-share filenya ke email bot sebagai Editor!")
        st.stop()
        
    try:
        worksheet = sh.worksheet(st.session_state.username)
    except gspread.exceptions.WorksheetNotFound:
        # Bot bakal nyari tab 'Template' dan nge-duplikat semua desain, border, & rumusnya!
        try:
            template_sheet = sh.worksheet("Template")
            worksheet = sh.duplicate_sheet(
                source_sheet_id=template_sheet.id,
                new_sheet_name=st.session_state.username
            )
        except gspread.exceptions.WorksheetNotFound:
            st.error("❌ Tab 'Template' belum ada! Bikin dulu tab bernama Template di Google Sheets lu.")
            st.stop()

total_masuk_str = worksheet.acell('F2').value or '0'
total_keluar_str = worksheet.acell('G2').value or '0'
saldo_str = worksheet.acell('H2').value or '0'

col1, col2, col3 = st.columns(3)
col1.metric("Pemasukan", f"Rp {total_masuk_str}")
col2.metric("Pengeluaran", f"Rp {total_keluar_str}")
col3.metric("Saldo Tersisa", f"Rp {saldo_str}")

# URL ngarah ke File Master, jadi temen lu bisa ngecek juga datanya
st.divider()
st.subheader("📋 Riwayat Transaksi")

with st.expander(f"Buka riwayat pengeluaran {st.session_state.username}"):
    # Narik semua data mentah dari tab milik user yang lagi login
    semua_data = worksheet.get_all_values()
    
    if len(semua_data) > 1:
        # Bikin jadi tabel pandas (DataFrame)
        df = pd.DataFrame(semua_data[1:], columns=semua_data[0])
        
        # Cuma ngambil 4 kolom pertama biar rapi (buang kolom saldo di kanan)
        df_transaksi = df[['Tanggal', 'Keterangan / Nama Barang', 'Jumlah', 'Pengeluaran (Rp)']]
        
        # Bersihin baris yang kosong (kalau ada)
        df_transaksi = df_transaksi[df_transaksi['Tanggal'].astype(bool) & (df_transaksi['Tanggal'] != '')]
        
        # Tampilkan tabel interaktif di dalam app
        st.dataframe(df_transaksi, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada riwayat transaksi.")
st.divider()

st.subheader("💰 Tambah Pemasukan")
with st.form("form_pemasukan"):
    pemasukan_baru = st.number_input("Nominal Uang Masuk (Rp)", min_value=0, step=10000)
    submit_pemasukan = st.form_submit_button("Update Pemasukan")
    
    if submit_pemasukan and pemasukan_baru > 0:
        total_saat_ini = int(re.sub(r'[^\d]', '', total_masuk_str)) if total_masuk_str else 0
        total_baru = total_saat_ini + int(pemasukan_baru)
        worksheet.update_acell('F2', total_baru)
        st.success(f"Berhasil ditambah! Saldo Pemasukan sekarang: Rp {total_baru:,}")
        st.rerun()

st.divider()

st.subheader("📝 Input Pengeluaran Manual")
with st.form("form_manual"):
    col_m1, col_m2 = st.columns([3, 1])
    with col_m1:
        nama_barang_manual = st.text_input("Keterangan / Nama Barang")
    with col_m2:
        jumlah_manual = st.text_input("Qty", value="1")
        
    nominal_manual = st.number_input("Nominal Pengeluaran (Rp)", min_value=0, step=1000)
    submit_manual = st.form_submit_button("Simpan Pengeluaran")
    
    if submit_manual:
        if not nama_barang_manual:
            st.warning("Isi keterangan barangnya dulu bro!")
        elif nominal_manual <= 0:
            st.warning("Isi nominal harganya yang bener bro!")
        else:
            with st.spinner("Menyimpan data..."):
                waktu_wib = datetime.utcnow() + timedelta(hours=7)
                tanggal_manual = waktu_wib.strftime("%d/%m/%Y")
                
                kolom_a = worksheet.col_values(1)
                baris_baru = 2
                for i, val in enumerate(kolom_a):
                    if val.strip() == '' and i > 0:
                        baris_baru = i + 1
                        break
                else:
                    baris_baru = len(kolom_a) + 1
                    
                range_target = f'A{baris_baru}:D{baris_baru}'
                row_to_insert = [tanggal_manual, nama_barang_manual, jumlah_manual, int(nominal_manual)]
                
                try:
                    worksheet.update(values=[row_to_insert], range_name=range_target)
                except TypeError:
                    worksheet.update(range_target, [row_to_insert])
                    
                st.success(f"✅ Sukses dicatat: {tanggal_manual} | Rp {int(nominal_manual):,}")
                st.rerun()

st.divider()

st.subheader("🧾 Upload Struk Pengeluaran")
uploaded_files = st.file_uploader("Pilih screenshot m-BCA atau e-Commerce", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

if uploaded_files:
    for file in uploaded_files:
        st.markdown(f"**Memproses:** `{file.name}`")
        
        col_a, col_b = st.columns([3, 1])
        with col_a:
            nama_barang = st.text_input(f"Keterangan ({file.name})", key=f"nama_{file.name}")
        with col_b:
            jumlah = st.text_input(f"Qty ({file.name})", value="1", key=f"qty_{file.name}")
        
        if st.button(f"Proses & Simpan: {file.name}", key=f"btn_{file.name}"):
            if not nama_barang:
                st.warning("Isi keterangan barangnya dulu bro!")
            else:
                with st.spinner("Mengekstrak teks..."):
                    file_bytes = np.frombuffer(file.read(), np.uint8)
                    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    
                    extracted_text = pytesseract.image_to_string(thresh).upper()
                    
                    date_match = re.search(r'(\d{2}/\d{2}(?:/\d{4})?)', extracted_text)
                    if date_match:
                        tanggal = date_match.group(1)
                    else:
                        waktu_wib = datetime.utcnow() + timedelta(hours=7)
                        tanggal = waktu_wib.strftime("%d/%m/%Y")
                    
                    clean_nominal = None
                    
                    bca_amounts = re.findall(r'RP[^\d]*(\d{1,3}(?:\.\d{3})*)', extracted_text)
                    if bca_amounts:
                        clean_nominal = int(bca_amounts[-1].replace('.', ''))
                        
                    if not clean_nominal:
                        umum_match = re.search(r'TOTAL(?: PEMBAYARAN)?[^\d]*([\d\.]+)', extracted_text)
                        if umum_match:
                            clean_nominal = int(umum_match.group(1).replace('.', ''))
                    
                    if clean_nominal:
                        kolom_a = worksheet.col_values(1)
                        baris_baru = 2
                        for i, val in enumerate(kolom_a):
                            if val.strip() == '' and i > 0:
                                baris_baru = i + 1
                                break
                        else:
                            baris_baru = len(kolom_a) + 1
                            
                        range_target = f'A{baris_baru}:D{baris_baru}'
                        row_to_insert = [tanggal, nama_barang, jumlah, clean_nominal]
                        
                        try:
                            worksheet.update(values=[row_to_insert], range_name=range_target)
                        except TypeError:
                            worksheet.update(range_target, [row_to_insert])
                            
                        st.success(f"✅ Sukses dicatat: {tanggal} | Rp {clean_nominal:,}")
                        st.rerun()
                    else:
                        st.error("❌ Gagal deteksi nominal. Coba cek gambar.")
