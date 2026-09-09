import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# ==========================================
# PAGE CONFIGURATION & CSS
# ==========================================
st.set_page_config(page_title="Expenses Tracker SaaS", page_icon="💸", layout="centered")

hide_pull_to_refresh = """
    <style>
    html, body, .stApp { overscroll-behavior: none !important; }
    /* Enhance login form UI */
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
# SYSTEM CONNECTION
# ==========================================
@st.cache_resource
def init_connection():
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

gc = init_connection()
MASTER_SHEET_NAME = "Tracker Master SaaS"

# ==========================================
# LOGIN & REGISTER PAGE
# ==========================================
if st.session_state.username is None:
    st.markdown("<h1 style='text-align: center; color: #1E88E5;'>💸 Expenses Tracker SaaS</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; margin-bottom: 30px;'>Please login or create an account</p>", unsafe_allow_html=True)
    
    # Connect to 'Users' Tab in Master Sheet
    try:
        sh = gc.open(MASTER_SHEET_NAME)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ File '{MASTER_SHEET_NAME}' not found. Make sure the bot is invited as an Editor.")
        st.stop()
        
    try:
        users_sheet = sh.worksheet("Users")
    except gspread.exceptions.WorksheetNotFound:
        # Auto-create Users tab if missing
        users_sheet = sh.add_worksheet(title="Users", rows=1000, cols=2)
        users_sheet.insert_row(["Username", "Password"], 1)

    # Login & Register Tabs
    tab_login, tab_register = st.tabs(["🔑 LOGIN", "📝 REGISTER"])
    
    # --- LOGIN TAB ---
    with tab_login:
        with st.form("form_login"):
            login_user = st.text_input("Username")
            login_pass = st.text_input("Password", type="password")
            submit_login = st.form_submit_button("Login", use_container_width=True)
            
            if submit_login:
                if not login_user or not login_pass:
                    st.warning("Please enter your username and password!")
                else:
                    users_data = users_sheet.get_all_records()
                    if not users_data:
                        st.error("❌ No accounts registered yet. Please register first.")
                    else:
                        df_users = pd.DataFrame(users_data)
                        df_users.columns = df_users.columns.str.strip()
                        
                        # Verify credentials
                        user_match = df_users[(df_users['Username'].astype(str).str.lower() == login_user.lower()) & (df_users['Password'].astype(str) == login_pass)]
                        
                        if not user_match.empty:
                            st.session_state.username = login_user.lower()
                            st.rerun()
                        else:
                            st.error("❌ Invalid Username or Password!")

    # --- REGISTER TAB ---
    with tab_register:
        with st.form("form_register"):
            reg_user = st.text_input("Choose Username")
            reg_pass = st.text_input("Create Password", type="password")
            reg_pass2 = st.text_input("Confirm Password", type="password")
            submit_reg = st.form_submit_button("Create Account", use_container_width=True)
            
            if submit_reg:
                if not reg_user or not reg_pass:
                    st.warning("Fields cannot be empty!")
                elif reg_pass != reg_pass2:
                    st.error("❌ Passwords do not match!")
                else:
                    users_data = users_sheet.get_all_records()
                    if users_data:
                        df_users = pd.DataFrame(users_data)
                        if reg_user.lower() in df_users['Username'].astype(str).str.lower().values:
                            st.error("❌ Username already taken. Please choose another one!")
                            st.stop()
                    
                    # Append new account
                    users_sheet.append_row([reg_user.lower(), reg_pass])
                    st.success("✅ Account created successfully! Please switch to the LOGIN tab.")

    st.stop()

# ==========================================
# MAIN APP (POST-LOGIN)
# ==========================================
genai.configure(api_key=st.secrets["gemini_api_key"])
model = genai.GenerativeModel('gemini-1.5-flash')

col_title, col_logout = st.columns([3, 1])
with col_title:
    st.title("💸 Financial Dashboard")
with col_logout:
    if st.button("🚪 Logout"):
        st.session_state.username = None
        st.rerun()
st.caption(f"👤 Logged in as: **{st.session_state.username}**")

# Open user-specific database
with st.spinner("Preparing dashboard..."):
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
            st.error("❌ 'Template' tab is missing in your Google Sheets.")
            st.stop()

# FETCH BALANCE DATA
total_masuk_str = worksheet.acell('F2').value or '0'
total_keluar_str = worksheet.acell('G2').value or '0'
saldo_str = worksheet.acell('H2').value or '0'

col1, col2, col3 = st.columns(3)
col1.metric("Income", f"Rp {total_masuk_str}")
col2.metric("Expenses", f"Rp {total_keluar_str}")
col3.metric("Balance", f"Rp {saldo_str}")

# TRANSACTION HISTORY (PANDAS)
st.divider()
with st.expander(f"📋 View Transaction History"):
    semua_data = worksheet.get_all_values()
    if len(semua_data) > 1:
        df = pd.DataFrame(semua_data[1:], columns=semua_data[0])
        df_transaksi = df[['Tanggal', 'Keterangan / Nama Barang', 'Jumlah', 'Pengeluaran (Rp)']]
        df_transaksi = df_transaksi[df_transaksi['Tanggal'].astype(bool) & (df_transaksi['Tanggal'] != '')]
        
        # Translate column headers for UI display only
        df_transaksi.columns = ['Date', 'Description', 'Qty', 'Total Expense (Rp)']
        st.dataframe(df_transaksi, use_container_width=True, hide_index=True)
    else:
        st.info("No transaction history yet.")

# ADD MANUAL INCOME
st.divider()
st.subheader("💰 Add Income")
with st.form("form_pemasukan"):
    pemasukan_baru = st.number_input("Income Amount (Rp)", min_value=0, step=10000)
    if st.form_submit_button("Update Income", use_container_width=True) and pemasukan_baru > 0:
        total_saat_ini = int(total_masuk_str.replace('.', '').replace(',', '')) if total_masuk_str else 0
        worksheet.update_acell('F2', total_saat_ini + int(pemasukan_baru))
        st.success("Successfully added!")
        st.rerun()

# ADD MANUAL EXPENSE
st.divider()
st.subheader("📝 Add Manual Expense")
with st.form("form_manual"):
    col_m1, col_m2 = st.columns([3, 1])
    with col_m1:
        nama_barang_manual = st.text_input("Description / Item Name")
    with col_m2:
        jumlah_manual = st.number_input("Qty", min_value=1, value=1)
        
    nominal_manual = st.number_input("Unit Price (Rp)", min_value=0, step=1000)
    
    if st.form_submit_button("Save Expense", use_container_width=True):
        if nama_barang_manual and nominal_manual > 0:
            with st.spinner("Storing..."):
                total_pengeluaran = int(nominal_manual) * jumlah_manual
                
                tanggal_manual = (datetime.utcnow() + timedelta(hours=7)).strftime("%d/%m/%Y")
                baris_baru = len(list(filter(None, worksheet.col_values(1)))) + 1
                
                worksheet.update(
                    values=[[tanggal_manual, nama_barang_manual, str(jumlah_manual), total_pengeluaran]], 
                    range_name=f'A{baris_baru}:D{baris_baru}'
                )
                
                total_keluar_now = int(str(total_keluar_str).replace('.', '').replace(',', '')) if total_keluar_str else 0
                total_masuk_now = int(str(total_masuk_str).replace('.', '').replace(',', '')) if total_masuk_str else 0
                
                pengeluaran_baru = total_keluar_now + total_pengeluaran
                saldo_baru = total_masuk_now - pengeluaran_baru
                
                worksheet.update(values=[[pengeluaran_baru, saldo_baru]], range_name='G2:H2')
                
                st.success(f"✅ Success! Total: Rp {total_pengeluaran:,}")
                st.rerun()
        else:
            st.warning("Please enter a valid description and unit price!")

# ==========================================
# UPLOAD RECEIPT AI (Fully Auto for all types)
# ==========================================
st.divider()
st.subheader("🤖 Upload Receipt")
st.write("Upload M-Banking, E-Commerce, or Shopping Receipts.")

with st.form("form_ai_otomatis"):
    uploaded_file = st.file_uploader("Upload receipt here", type=['png', 'jpg', 'jpeg'])
    submit_ai = st.form_submit_button("Process Receipt", use_container_width=True)

    if submit_ai:
        if uploaded_file is None:
            st.warning("⚠️ Please upload your receipt first!")
        else:
            with st.spinner("The receipt is being processed..."):
                try:
                    image = Image.open(uploaded_file)
                    
                    prompt = """
                    Analyze this receipt, e-commerce invoice, or M-Banking transfer proof image. 
                    Your task is to extract the main data into a pure JSON format without markdown text (no ```json prefix).
                    
                    Extraction rules:
                    1. "tanggal": Format DD/MM/YYYY. If not found, leave blank "".
                    2. "keterangan": 
                       - If M-Banking: Write the transfer recipient / institution name.
                       - If E-commerce (1 type of item): Write the item name briefly.
                       - If Bulk Shopping Receipt: Write the store name only (e.g., "Grocery at Walmart", "Dinner at McD").
                    3. "jumlah": 
                       - If a specific item has a quantity, write the number (e.g., 2, 3).
                       - If it's a transfer, top-up, or bulk shopping receipt, write 1.
                    4. "harga_satuan": 
                       - Price per 1 pcs of item, OR
                       - Grand Total (if it's a bulk shopping receipt / m-banking transfer). Pure number without dots/commas/currency.

                    MANDATORY JSON format to return:
                    {
                        "tanggal": "25/12/2023",
                        "keterangan": "Topup Gopay / Fried Rice",
                        "jumlah": 1,
                        "harga_satuan": 50000
                    }
                    """
                    response = model.generate_content([prompt, image])
                    res_text = response.text.replace("```json", "").replace("```", "").strip()
                    data = json.loads(res_text)
                    
                    tanggal = data.get("tanggal", "")
                    if not tanggal:
                        tanggal = (datetime.utcnow() + timedelta(hours=7)).strftime("%d/%m/%Y")
                        
                    nama_barang_ai = data.get("keterangan", "Expense (AI)")
                    jumlah_ai = int(data.get("jumlah", 1)) 
                    harga_satuan = int(data.get("harga_satuan", 0))
                    
                    if harga_satuan > 0:
                        harga_akhir = harga_satuan * jumlah_ai
                        
                        baris_baru = len(list(filter(None, worksheet.col_values(1)))) + 1
                        worksheet.update(
                            values=[[tanggal, nama_barang_ai, str(jumlah_ai), harga_akhir]], 
                            range_name=f'A{baris_baru}:D{baris_baru}'
                        )
                        
                        total_keluar_now = int(str(total_keluar_str).replace('.', '').replace(',', '')) if total_keluar_str else 0
                        total_masuk_now = int(str(total_masuk_str).replace('.', '').replace(',', '')) if total_masuk_str else 0
                        
                        pengeluaran_baru = total_keluar_now + harga_akhir
                        saldo_baru = total_masuk_now - pengeluaran_baru
                        
                        worksheet.update(values=[[pengeluaran_baru, saldo_baru]], range_name='G2:H2')
                        
                        st.success(f"✅ Receipt found: **{nama_barang_ai}** | Rp {harga_satuan:,} x {jumlah_ai} (Qty). Total: Rp {harga_akhir:,}")
                        st.rerun()
                    else:
                        st.error("❌ The receipt could not be read. Please ensure the receipt image is clear and readable.")
                        
                except Exception as e:
                    st.error(f"Failed to process receipt. (Error: {e})")
