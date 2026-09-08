import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

st.set_page_config(page_title="BCA Tracker SaaS", page_icon="💸", layout="centered")

# CSS Anti-Refresh
hide_pull_to_refresh = """
    <style>
    html, body, .stApp { overscroll-behavior: none !important; }
    </style>
"""
st.markdown(hide_pull_to_refresh, unsafe_allow_html=True)

# Inisialisasi Akun User
if 'username' not in st.session_state:
    st.session_state.username = None

# ==========================================
# HALAMAN LOGIN
# ==========================================
if st.session_state.username is None:
    st.title("👋 Welcome to Tracker Keuangan")
    st.write("Tiap pengguna akan dapet Tab Database masing-masing secara otomatis!")
    with st.form("login_form"):
        username_input = st.text_input("Masukkan Username (Tanpa spasi):")
        submit_login = st.form_submit_button("Masuk Aplikasi")
        if submit_login:
            if username_input.strip() == "":
                st.warning("Nama gak boleh kosong bro!")
            else:
                st.session_state.username = username_input.strip().lower()
                st.rerun()
    st.stop()

# ==========================================
# MAIN APP & OTENTIKASI
# ==========================================
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

# SETUP GEMINI AI
genai.configure(api_key=st.secrets["gemini_api_key"])
model = genai.GenerativeModel('gemini-1.5-flash')

MASTER_SHEET_NAME = "Tracker Master SaaS"

# SETUP DATABASE MASTER SHEET
with st.spinner(f"Membuka database untuk {st.session_state.username}..."):
    try:
        sh = gc.open(MASTER_SHEET_NAME)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ File '{MASTER_SHEET_NAME}' belum ada atau lu belum nge-share filenya ke email bot sebagai Editor!")
        st.stop()
        
    try:
        worksheet = sh.worksheet(st.session_state.username)
    except gspread.exceptions.WorksheetNotFound:
        try:
            template_sheet = sh.worksheet("Template")
            worksheet = sh.duplicate_sheet(
                source_sheet_id=template_sheet.id,
                new_sheet_name=st.session_state.username
            )
        except gspread.exceptions.WorksheetNotFound:
            st.error("❌ Tab 'Template' belum ada di dalam Google Sheets lu.")
            st.stop()

# AMBIL DATA SALDO
total_masuk_str = worksheet.acell('F2').value or '0'
total_keluar_str = worksheet.acell('G2').value or '0'
saldo_str = worksheet.acell('H2').value or '0'

col1, col2, col3 = st.columns(3)
col1.metric("Pemasukan", f"Rp {total_masuk_str}")
col2.metric("Pengeluaran", f"Rp {total_keluar_str}")
col3.metric("Saldo Tersisa", f"Rp {saldo_str}")

# ==========================================
# RIWAYAT TRANSAKSI (PANDAS)
# ==========================================
st.divider()
with st.expander(f"📋 Buka Riwayat Transaksi {st.session_state.username}"):
    semua_data = worksheet.get_all_values()
    if len(semua_data) > 1:
        df = pd.DataFrame(semua_data[1:], columns=semua_data[0])
        df_transaksi = df[['Tanggal', 'Keterangan / Nama Barang', 'Jumlah', 'Pengeluaran (Rp)']]
        df_transaksi = df_transaksi[df_transaksi['Tanggal'].astype(bool) & (df_transaksi['Tanggal'] != '')]
        st.dataframe(df_transaksi, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada riwayat transaksi.")

# ==========================================
# TAMBAH PEMASUKAN & PENGELUARAN MANUAL
# ==========================================
st.divider()
st.subheader("💰 Tambah Pemasukan")
with st.form("form_pemasukan"):
    pemasukan_baru = st.number_input("Nominal Uang Masuk (Rp)", min_value=0, step=10000)
    if st.form_submit_button("Update Pemasukan") and pemasukan_baru > 0:
        total_saat_ini = int(total_masuk_str.replace('.', '').replace(',', '')) if total_masuk_str else 0
        worksheet.update_acell('F2', total_saat_ini + int(pemasukan_baru))
        st.success("Berhasil ditambah!")
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
    
    if st.form_submit_button("Simpan Pengeluaran"):
        if nama_barang_manual and nominal_manual > 0:
            with st.spinner("Menyimpan..."):
                tanggal_manual = (datetime.utcnow() + timedelta(hours=7)).strftime("%d/%m/%Y")
                baris_baru = len(list(filter(None, worksheet.col_values(1)))) + 1
                worksheet.update(values=[[tanggal_manual, nama_barang_manual, jumlah_manual, int(nominal_manual)]], range_name=f'A{baris_baru}:D{baris_baru}')
                st.success("✅ Sukses dicatat!")
                st.rerun()
        else:
            st.warning("Isi keterangan dan nominal dengan benar!")

# ==========================================
# UPLOAD STRUK (GOOGLE GEMINI AI)
# ==========================================
st.divider()
st.subheader("🤖 Upload Struk (Dibaca oleh AI)")
uploaded_files = st.file_uploader("Upload screenshot m-BCA atau e-Commerce", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

if uploaded_files:
    for file in uploaded_files:
        st.markdown(f"**Memproses:** `{file.name}`")
        if st.button(f"Minta AI Baca Struk: {file.name}", key=f"btn_{file.name}"):
            with st.spinner("AI sedang membaca struk lu..."):
                try:
                    # Buka gambar dan minta Gemini menganalisis
                    image = Image.open(file)
                    prompt = """
                    Analisis gambar struk/bukti transfer ini. Ekstrak informasi berikut dan kembalikan HANYA dalam format JSON murni tanpa teks awalan/akhiran apapun:
                    {
                        "tanggal": "DD/MM/YYYY",
                        "keterangan": "Tuliskan nama toko atau penerima transfer",
                        "total": 50000
                    }
                    Catatan:
                    1. Jika tanggal tidak ada, kosongkan nilainya.
                    2. Nilai "total" harus berupa angka integer tanpa titik, koma, atau Rp.
                    """
                    response = model.generate_content([prompt, image])
                    
                    # Bersihkan teks hasil AI dan ubah jadi JSON
                    res_text = response.text.replace("```json", "").replace("```", "").strip()
                    data = json.loads(res_text)
                    
                    # Set variabel untuk dikirim ke Google Sheets
                    tanggal = data.get("tanggal", "")
                    if not tanggal:
                        tanggal = (datetime.utcnow() + timedelta(hours=7)).strftime("%d/%m/%Y")
                        
                    nama_barang = data.get("keterangan", "Pengeluaran (AI)")
                    clean_nominal = int(data.get("total", 0))
                    
                    if clean_nominal > 0:
                        baris_baru = len(list(filter(None, worksheet.col_values(1)))) + 1
                        worksheet.update(values=[[tanggal, nama_barang, "1", clean_nominal]], range_name=f'A{baris_baru}:D{baris_baru}')
                        st.success(f"✅ Sukses dicatat oleh AI: {tanggal} | {nama_barang} | Rp {clean_nominal:,}")
                        st.rerun()
                    else:
                        st.error("❌ AI tidak menemukan nominal pengeluaran di gambar ini.")
                        
                except Exception as e:
                    st.error(f"Gagal diproses AI. Pastikan gambar jelas. (Error: {e})")
