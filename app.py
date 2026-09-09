import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# ==========================================
# KONFIGURASI HALAMAN & CSS
# ==========================================
st.set_page_config(page_title="Expenses Tracker SaaS", page_icon="💸", layout="centered")

hide_pull_to_refresh = """
    <style>
    html, body, .stApp { overscroll-behavior: none !important; }
    /* Mempercantik tampilan form login */
    div[data-testid="stForm"] {
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    </style>
"""
st.markdown(hide_pull_to_refresh, unsafe_allow_html=True)

if 'username' not in st.session_state:
    st.session_state.username = None

# ==========================================
# KONEKSI SISTEM (DIPINDAH KE ATAS)
# ==========================================
@st.cache_resource
def init_connection():
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

gc = init_connection()
MASTER_SHEET_NAME = "Tracker Master SaaS"

# ==========================================
# HALAMAN LOGIN & REGISTER SOLID
# ==========================================
if st.session_state.username is None:
    # Bikin judul di tengah
    st.markdown("<h1 style='text-align: center; color: #1E88E5;'>💸 Tracker Keuangan SaaS</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; margin-bottom: 30px;'>Silakan masuk atau buat akun untuk mengakses database Anda</p>", unsafe_allow_html=True)
    
    # Hubungkan ke Tab 'Users' di Master Sheet
    try:
        sh = gc.open(MASTER_SHEET_NAME)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ File '{MASTER_SHEET_NAME}' belum ada. Pastikan bot sudah di-invite sebagai Editor.")
        st.stop()
        
    try:
        users_sheet = sh.worksheet("Users")
    except gspread.exceptions.WorksheetNotFound:
        # Bot otomatis bikin tab Users kalau belum ada
        users_sheet = sh.add_worksheet(title="Users", rows=1000, cols=2)
        users_sheet.insert_row(["Username", "Password"], 1)

    # Layout Tab Login & Register
    tab_login, tab_register = st.tabs(["🔑 MASUK", "📝 DAFTAR BARU"])
    
    # --- TAB LOGIN ---
    with tab_login:
        with st.form("form_login"):
            login_user = st.text_input("Username")
            login_pass = st.text_input("Password", type="password") # Input disensor
            submit_login = st.form_submit_button("Masuk Aplikasi", use_container_width=True)
            
            if submit_login:
                if not login_user or not login_pass:
                    st.warning("Mohon isi username dan password terlebih dahulu!")
                else:
                    users_data = users_sheet.get_all_records()
                    if not users_data:
                        st.error("❌ Belum ada akun yang terdaftar. Silakan daftar dulu.")
                    else:
                        df_users = pd.DataFrame(users_data)
                        df_users.columns = df_users.columns.str.strip() # Bersihin spasi
                        
                        # Cek kecocokan di database
                        user_match = df_users[(df_users['Username'].astype(str).str.lower() == login_user.lower()) & (df_users['Password'].astype(str) == login_pass)]
                        
                        if not user_match.empty:
                            st.session_state.username = login_user.lower()
                            st.rerun()
                        else:
                            st.error("❌ Username atau Password salah!")

    # --- TAB REGISTER ---
    with tab_register:
        with st.form("form_register"):
            reg_user = st.text_input("Pilih Username")
            reg_pass = st.text_input("Buat Password", type="password")
            reg_pass2 = st.text_input("Konfirmasi Password", type="password")
            submit_reg = st.form_submit_button("Buat Akun", use_container_width=True)
            
            if submit_reg:
                if not reg_user or not reg_pass:
                    st.warning("Data nggak boleh kosong!")
                elif reg_pass != reg_pass2:
                    st.error("❌ Password nggak cocok bro!")
                else:
                    users_data = users_sheet.get_all_records()
                    if users_data:
                        df_users = pd.DataFrame(users_data)
                        if reg_user.lower() in df_users['Username'].astype(str).str.lower().values:
                            st.error("❌ Username udah dipakai orang lain. Cari nama lain!")
                            st.stop()
                    
                    # Tambahin akun baru ke sheet
                    users_sheet.append_row([reg_user.lower(), reg_pass])
                    st.success("✅ Akun sukses dibuat! Silakan pindah ke tab MASUK.")

    st.stop() # Berhentiin kode di sini kalau belum berhasil login

# ==========================================
# MAIN APP (JALAN SETELAH LOGIN)
# ==========================================
genai.configure(api_key=st.secrets["gemini_api_key"])
model = genai.GenerativeModel('gemini-3.5-flash')

col_title, col_logout = st.columns([3, 1])
with col_title:
    st.title("💸 Dashboard Keuangan")
with col_logout:
    if st.button("🚪 Keluar"):
        st.session_state.username = None
        st.rerun()
st.caption(f"👤 Login sebagai: **{st.session_state.username}**")

# Buka database khusus user ini
with st.spinner("Menyiapkan dashboard"):
    sh = gc.open(MASTER_SHEET_NAME)
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
col3.metric("Saldo", f"Rp {saldo_str}")

# RIWAYAT TRANSAKSI (PANDAS)
st.divider()
with st.expander(f"📋 Buka Riwayat Transaksi"):
    semua_data = worksheet.get_all_values()
    if len(semua_data) > 1:
        df = pd.DataFrame(semua_data[1:], columns=semua_data[0])
        df_transaksi = df[['Tanggal', 'Keterangan / Nama Barang', 'Jumlah', 'Pengeluaran (Rp)']]
        df_transaksi = df_transaksi[df_transaksi['Tanggal'].astype(bool) & (df_transaksi['Tanggal'] != '')]
        st.dataframe(df_transaksi, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada riwayat transaksi.")

# TAMBAH PEMASUKAN MANUAL
st.divider()
st.subheader("💰 Tambah Pemasukan")
with st.form("form_pemasukan"):
    pemasukan_baru = st.number_input("Nominal Uang Masuk (Rp)", min_value=0, step=10000)
    if st.form_submit_button("Update Pemasukan", use_container_width=True) and pemasukan_baru > 0:
        total_saat_ini = int(total_masuk_str.replace('.', '').replace(',', '')) if total_masuk_str else 0
        worksheet.update_acell('F2', total_saat_ini + int(pemasukan_baru))
        st.success("Berhasil ditambah!")
        st.rerun()

# TAMBAH PENGELUARAN MANUAL
st.divider()
st.subheader("📝 Input Pengeluaran Manual")
with st.form("form_manual"):
    col_m1, col_m2 = st.columns([3, 1])
    with col_m1:
        nama_barang_manual = st.text_input("Keterangan / Nama Barang")
    with col_m2:
        jumlah_manual = st.text_input("Qty", value="1")
    nominal_manual = st.number_input("Nominal Pengeluaran (Rp)", min_value=0, step=1000)
    
    if st.form_submit_button("Simpan Pengeluaran", use_container_width=True):
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
# UPLOAD STRUK AI (Kombinasi Manual + AI)
# ==========================================
st.divider()
st.subheader("🤖 Upload Struk (Manual + AI)")
st.write("Isi nama & jumlah barang manual, biar AI yang nyari harganya dari struk!")

with st.form("form_ai_manual"):
    # Bikin inputan sejajar biar rapi
    col_ai1, col_ai2 = st.columns([3, 1])
    with col_ai1:
        nama_barang_ai = st.text_input("Keterangan / Nama Barang")
    with col_ai2:
        jumlah_ai = st.number_input("Qty", min_value=1, value=1)
        
    uploaded_file = st.file_uploader("Upload screenshot struk", type=['png', 'jpg', 'jpeg'])
    
    # Tombol submit-nya ada di dalam form
    submit_ai = st.form_submit_button("Proses dengan AI", use_container_width=True)

    if submit_ai:
        if not nama_barang_ai:
            st.warning("⚠️ Isi dulu Keterangan / Nama Barang-nya bro!")
        elif uploaded_file is None:
            st.warning("⚠️ Upload dulu gambar struknya!")
        else:
            with st.spinner("AI sedang melototin harga di struk..."):
                try:
                    image = Image.open(uploaded_file)
                    
                    # Prompt AI dirubah: Cuma disuruh nyari harga
                    prompt = """
                    Analisis gambar struk/bukti transfer ini. Temukan harga satuan barang atau total nominal transfer.
                    Kembalikan HANYA dalam format JSON murni tanpa teks awalan/akhiran:
                    {
                        "tanggal": "DD/MM/YYYY",
                        "harga": 50000
                    }
                    Jika tanggal tidak ada, kosongkan nilainya. Nilai "harga" harus angka integer murni tanpa titik.
                    """
                    response = model.generate_content([prompt, image])
                    res_text = response.text.replace("```json", "").replace("```", "").strip()
                    data = json.loads(res_text)
                    
                    tanggal = data.get("tanggal", "")
                    if not tanggal:
                        tanggal = (datetime.utcnow() + timedelta(hours=7)).strftime("%d/%m/%Y")
                        
                    # AI cuma ngambil angka harga
                    harga_dari_ai = int(data.get("harga", 0))
                    
                    if harga_dari_ai > 0:
                        # LOGIKA MATEMATIKA LU DI SINI: Harga Akhir = Harga AI x Jumlah Manual
                        harga_akhir = harga_dari_ai * jumlah_ai
                        
                        # Simpan ke Google Sheets
                        baris_baru = len(list(filter(None, worksheet.col_values(1)))) + 1
                        worksheet.update(
                            values=[[tanggal, nama_barang_ai, str(jumlah_ai), harga_akhir]], 
                            range_name=f'A{baris_baru}:D{baris_baru}'
                        )
                        
                        st.success(f"✅ AI nemu harga Rp {harga_dari_ai:,} x {jumlah_ai} (Qty). Total tersimpan: Rp {harga_akhir:,}")
                    else:
                        st.error("❌ AI gagal nemuin angka harga di gambar ini. Coba foto yang lebih jelas.")
                        
                except Exception as e:
                    st.error(f"Gagal diproses. Pastikan gambar jelas. (Error: {e})")
