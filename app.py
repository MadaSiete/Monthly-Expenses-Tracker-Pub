import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import requests

# ==========================================
# PAGE CONFIGURATION & CSS
# ==========================================
st.set_page_config(page_title="Expenses Tracker Global", page_icon="💸", layout="centered")

elegant_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');

    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }

    .stApp {
        background: linear-gradient(rgba(15, 32, 39, 0.75), rgba(32, 58, 67, 0.75)), 
                    url("https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=2564&auto=format&fit=crop");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        color: #e0e0e0;
    }
    
    .block-container {
        max-width: 850px !important;
        padding-top: 3rem !important;
        padding-bottom: 3rem !important;
    }

    [data-testid="stHeader"] { background: transparent !important; }

    div[data-testid="stForm"], div[data-testid="metric-container"], .stExpander, div[data-testid="stVerticalBlock"] > div > div > div > div.stAlert {
        background: rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(16px) saturate(180%);
        -webkit-backdrop-filter: blur(16px) saturate(180%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
        padding: 20px;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    div[data-testid="metric-container"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.6);
    }

    div[data-testid="metric-container"] label {
        color: #b0bec5 !important;
        font-weight: 400;
        letter-spacing: 1px;
    }
    div[data-testid="stMetricValue"] > div {
        color: #ffffff !important;
        font-weight: 600;
        font-size: clamp(1.1rem, 2.5vw, 1.8rem) !important; 
        white-space: nowrap !important;
        text-overflow: clip !important; 
        overflow: visible !important;
    }

    div.stButton > button, div[data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 10px 24px !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0, 242, 254, 0.3) !important;
    }
    
    div.stButton > button:hover, div[data-testid="stFormSubmitButton"] > button:hover {
        transform: scale(1.02);
        box-shadow: 0 6px 20px rgba(0, 242, 254, 0.6) !important;
    }

    div[data-baseweb="input"], div[data-baseweb="base-input"], div[data-baseweb="select"] > div {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 10px !important;
    }
    div[data-baseweb="input"] input {
        color: white !important;
        background-color: transparent !important;
        padding: 12px !important;
    }
    div[data-baseweb="input"]:focus-within {
        border-color: #00f2fe !important;
        box-shadow: 0 0 10px rgba(0, 242, 254, 0.3) !important;
    }

    [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 10px; background-color: transparent !important; }
    [data-testid="stTabs"] [data-baseweb="tab-panel"] {
        background: rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-top: none;
        border-radius: 0 0 20px 20px;
        padding: 20px;
    }

    [data-testid="stTable"] {
        background: rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(16px);
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    [data-testid="stTable"] table { color: white !important; background: transparent !important; width: 100%; }
    [data-testid="stTable"] th { background-color: rgba(0, 242, 254, 0.1) !important; color: #00f2fe !important; border-bottom: 1px solid rgba(255, 255, 255, 0.2) !important; }
    [data-testid="stTable"] td { background: transparent !important; border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important; }
    [data-testid="stTable"] th:first-child, [data-testid="stTable"] td:first-child { display: none; }

    html, body { overscroll-behavior: none !important; }
    [data-testid="stSidebarNav"], [data-testid="collapsedControl"] { display: none; }
    footer {visibility: hidden;}
    </style>
"""
st.markdown(elegant_css, unsafe_allow_html=True)

# ==========================================
# SESSION STATES & GLOBALS
# ==========================================
if 'username' not in st.session_state:
    st.session_state.username = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'home'

# Daftar Mata Uang Global
CURRENCY_DATA = {
    "IDR": "Rp", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", 
    "SGD": "S$", "MYR": "RM", "AUD": "A$", "CAD": "C$"
}

if 'currency' not in st.session_state:
    st.session_state.currency = 'IDR'
if 'currency_symbol' not in st.session_state:
    st.session_state.currency_symbol = 'Rp'

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
    st.markdown("<h1 style='text-align: center; color: #1E88E5;'>💸 Expenses Tracker</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; margin-bottom: 30px;'>Sign in to your account</p>", unsafe_allow_html=True)
    
    try:
        sh = gc.open(MASTER_SHEET_NAME)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ File '{MASTER_SHEET_NAME}' not found.")
        st.stop()
        
    try:
        users_sheet = sh.worksheet("Users")
    except gspread.exceptions.WorksheetNotFound:
        users_sheet = sh.add_worksheet(title="Users", rows=1000, cols=2)
        users_sheet.insert_row(["Username", "Password"], 1)

    tab_login, tab_register = st.tabs(["🔑 LOGIN", "📝 REGISTER"])
    
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
                        user_match = df_users[(df_users['Username'].astype(str).str.lower() == login_user.lower()) & (df_users['Password'].astype(str) == login_pass)]
                        
                        if not user_match.empty:
                            st.session_state.username = login_user.lower()
                            st.session_state.current_page = 'home'
                            st.rerun()
                        else:
                            st.error("❌ Invalid Username or Password!")

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
                            st.error("❌ Username already taken.")
                            st.stop()
                    
                    users_sheet.append_row([reg_user.lower(), reg_pass])
                    st.success("✅ Account created successfully! Switch to the LOGIN tab.")
    st.stop()

# ==========================================
# APP INITIALIZATION (POST-LOGIN)
# ==========================================
genai.configure(api_key=st.secrets["gemini_api_key"])
model = genai.GenerativeModel('gemini-1.5-flash')

with st.spinner("Loading data..."):
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
            st.error("❌ 'Template' tab is missing.")
            st.stop()

# FETCH BALANCE DATA
total_masuk_str = worksheet.acell('F2').value or '0'
total_keluar_str = worksheet.acell('G2').value or '0'
saldo_str = worksheet.acell('H2').value or '0'

sym = st.session_state.currency_symbol

# ==========================================
# PAGE 1: HOMESCREEN (MAIN MENU)
# ==========================================
if st.session_state.current_page == 'home':
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.title("💸 Expenses Tracker")
        st.caption(f"👤 Logged in as: **{st.session_state.username}**")
    with col_t2:
        # Currency Selector UI
        selected_curr = st.selectbox(
            "Currency", 
            options=list(CURRENCY_DATA.keys()), 
            index=list(CURRENCY_DATA.keys()).index(st.session_state.currency)
        )
        if selected_curr != st.session_state.currency:
            st.session_state.currency = selected_curr
            st.session_state.currency_symbol = CURRENCY_DATA[selected_curr]
            st.rerun()

    col1, col2, col3 = st.columns(3)
    col1.metric("Income", f"{sym} {total_masuk_str}")
    col2.metric("Expenses", f"{sym} {total_keluar_str}")
    col3.metric("Balance", f"{sym} {saldo_str}")

    st.divider()
    st.subheader("📌 Main Menu")

    btn_col1, btn_col2, btn_col3 = st.columns(3)
    with btn_col1:
        if st.button("💰 Add Income", use_container_width=True):
            st.session_state.current_page = 'income'
            st.rerun()
        if st.button("📝 Manual Expense", use_container_width=True):
            st.session_state.current_page = 'manual_expense'
            st.rerun()
    with btn_col2:
        if st.button("🤖 AI Scanner", use_container_width=True):
            st.session_state.current_page = 'ai_scanner'
            st.rerun()
        if st.button("📋 History", use_container_width=True):
            st.session_state.current_page = 'history'
            st.rerun()
    with btn_col3:
        if st.button("💱 Exchange Rate", use_container_width=True):
            st.session_state.current_page = 'exchange'
            st.rerun()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.username = None
            st.session_state.current_page = 'home'
            st.rerun()

# ==========================================
# PAGE 2: ADD INCOME
# ==========================================
elif st.session_state.current_page == 'income':
    if st.button("🏠 Back to Home", use_container_width=True):
        st.session_state.current_page = 'home'
        st.rerun()

    st.divider()
    st.title("💰 Add Income")
    
    with st.form("form_pemasukan"):
        pemasukan_baru = st.number_input(f"Income Amount ({sym})", min_value=0.0, step=10.0)
        if st.form_submit_button("Update Income", use_container_width=True) and pemasukan_baru > 0:
            total_saat_ini = float(str(total_masuk_str).replace('.', '').replace(',', '')) if total_masuk_str else 0
            worksheet.update_acell('F2', total_saat_ini + pemasukan_baru)
            st.success("Successfully added!")
            st.rerun()

# ==========================================
# PAGE 3: MANUAL EXPENSE
# ==========================================
elif st.session_state.current_page == 'manual_expense':
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("🏠 Home", use_container_width=True):
            st.session_state.current_page = 'home'
            st.rerun()
    with nav_col2:
        if st.button("📋 View History", use_container_width=True):
            st.session_state.current_page = 'history'
            st.rerun()

    st.divider()
    st.title("📝 Manual Expense")

    with st.form("form_manual"):
        col_m1, col_m2 = st.columns([3, 1])
        with col_m1:
            nama_barang_manual = st.text_input("Description / Item Name")
        with col_m2:
            jumlah_manual = st.number_input("Qty", min_value=1, value=1)
            
        nominal_manual = st.number_input(f"Unit Price ({sym})", min_value=0.0, step=5.0)
        
        if st.form_submit_button("Save Expense", use_container_width=True):
            if nama_barang_manual and nominal_manual > 0:
                with st.spinner("Storing..."):
                    total_pengeluaran = float(nominal_manual) * jumlah_manual
                    tanggal_manual = (datetime.utcnow() + timedelta(hours=7)).strftime("%d/%m/%Y")
                    baris_baru = len(list(filter(None, worksheet.col_values(1)))) + 1
                    
                    worksheet.update(
                        values=[[tanggal_manual, nama_barang_manual, str(jumlah_manual), total_pengeluaran]], 
                        range_name=f'A{baris_baru}:D{baris_baru}'
                    )
                    
                    total_keluar_now = float(str(total_keluar_str).replace('.', '').replace(',', '')) if total_keluar_str else 0
                    total_masuk_now = float(str(total_masuk_str).replace('.', '').replace(',', '')) if total_masuk_str else 0
                    
                    pengeluaran_baru = total_keluar_now + total_pengeluaran
                    saldo_baru = total_masuk_now - pengeluaran_baru
                    
                    worksheet.update(values=[[pengeluaran_baru, saldo_baru]], range_name='G2:H2')
                    st.success(f"✅ Success! Total: {sym} {total_pengeluaran:,}")
                    st.rerun()
            else:
                st.warning("Please enter a valid description and unit price!")

# ==========================================
# PAGE 4: AI RECEIPT SCANNER
# ==========================================
elif st.session_state.current_page == 'ai_scanner':
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("🏠 Home", use_container_width=True):
            st.session_state.current_page = 'home'
            st.rerun()
    with nav_col2:
        if st.button("📋 View History", use_container_width=True):
            st.session_state.current_page = 'history'
            st.rerun()

    st.divider()
    st.title("🤖 AI Receipt Scanner")
    
    with st.form("form_ai_otomatis"):
        st.caption("Optional: Override description for QRIS / unreadable receipts.")
        col_ai1, col_ai2 = st.columns([3, 1])
        with col_ai1:
            custom_name = st.text_input("Custom Description", placeholder="e.g., Dinner")
        with col_ai2:
            custom_qty = st.number_input("Qty", min_value=1, value=1)
            
        uploaded_file = st.file_uploader("Upload receipt here", type=['png', 'jpg', 'jpeg'])
        submit_ai = st.form_submit_button("Process Receipt", use_container_width=True)

        if submit_ai:
            if uploaded_file is None:
                st.warning("⚠️ Please upload your receipt first!")
            else:
                with st.spinner("Analyzing with AI..."):
                    try:
                        image = Image.open(uploaded_file)
                        prompt = """
                        Analyze this receipt, e-commerce invoice, or M-Banking/QRIS transfer proof image. 
                        Your task is to extract the main data into a pure JSON format without markdown text (no ```json prefix).
                        
                        1. "tanggal": Format DD/MM/YYYY. If not found, leave blank "".
                        2. "keterangan": Store name, item name, or transfer recipient.
                        3. "harga_satuan": Price per 1 pcs of item, OR Grand Total. Pure number (can include decimal). Do not include currency symbols.
                        """
                        response = model.generate_content([prompt, image])
                        res_text = response.text.replace("```json", "").replace("```", "").strip()
                        data = json.loads(res_text)
                        
                        tanggal = data.get("tanggal", "")
                        if not tanggal:
                            tanggal = (datetime.utcnow() + timedelta(hours=7)).strftime("%d/%m/%Y")
                            
                        nama_barang_ai = data.get("keterangan", "Expense (AI)")
                        final_nama = custom_name.strip() if custom_name.strip() != "" else nama_barang_ai
                        final_qty = custom_qty 
                        harga_satuan = float(data.get("harga_satuan", 0))
                        
                        if harga_satuan > 0:
                            harga_akhir = harga_satuan * final_qty
                            baris_baru = len(list(filter(None, worksheet.col_values(1)))) + 1
                            worksheet.update(
                                values=[[tanggal, final_nama, str(final_qty), harga_akhir]], 
                                range_name=f'A{baris_baru}:D{baris_baru}'
                            )
                            
                            total_keluar_now = float(str(total_keluar_str).replace('.', '').replace(',', '')) if total_keluar_str else 0
                            total_masuk_now = float(str(total_masuk_str).replace('.', '').replace(',', '')) if total_masuk_str else 0
                            
                            pengeluaran_baru = total_keluar_now + harga_akhir
                            saldo_baru = total_masuk_now - pengeluaran_baru
                            
                            worksheet.update(values=[[pengeluaran_baru, saldo_baru]], range_name='G2:H2')
                            st.success(f"✅ Processed: **{final_nama}** | {sym} {harga_satuan:,} x {final_qty}. Total: {sym} {harga_akhir:,}")
                            st.rerun()
                        else:
                            st.error("❌ The receipt could not be read.")
                    except Exception as e:
                        st.error(f"Failed to process receipt. (Error: {e})")

# ==========================================
# PAGE 5: TRANSACTION HISTORY
# ==========================================
elif st.session_state.current_page == 'history':
    if st.button("🏠 Back to Home", use_container_width=True):
        st.session_state.current_page = 'home'
        st.rerun()

    st.divider()
    st.title("📋 Transaction History")
    
    semua_data = worksheet.get_all_values()
    if len(semua_data) > 1:
        df = pd.DataFrame(semua_data[1:], columns=semua_data[0])
        df_transaksi = df[['Tanggal', 'Keterangan / Nama Barang', 'Jumlah', 'Pengeluaran (Rp)']]
        df_transaksi = df_transaksi[df_transaksi['Tanggal'].astype(bool) & (df_transaksi['Tanggal'] != '')]
        
        df_transaksi.columns = ['Date', 'Description', 'Qty', f'Total Expense ({sym})']
        st.table(df_transaksi)
    else:
        st.info("No transaction history yet.")

# ==========================================
# PAGE 6: CURRENCY EXCHANGE RATE (KURS)
# ==========================================
elif st.session_state.current_page == 'exchange':
    if st.button("🏠 Back to Home", use_container_width=True):
        st.session_state.current_page = 'home'
        st.rerun()

    st.divider()
    st.title("💱 Exchange Rate")
    st.write("Check live currency conversion rates globally.")
    
    with st.form("form_exchange"):
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            base_currency = st.selectbox("From", options=list(CURRENCY_DATA.keys()), index=list(CURRENCY_DATA.keys()).index(st.session_state.currency))
        with col_ex2:
            target_currency = st.selectbox("To", options=list(CURRENCY_DATA.keys()), index=1 if st.session_state.currency == 'IDR' else 0)
            
        amount_to_convert = st.number_input("Amount", min_value=0.0, value=1.0)
        
        if st.form_submit_button("Convert Currency", use_container_width=True):
            with st.spinner("Fetching live rates..."):
                try:
                    # Menggunakan Public API gratis tanpa key
                    url = f"[https://api.exchangerate-api.com/v4/latest/](https://api.exchangerate-api.com/v4/latest/){base_currency}"
                    response = requests.get(url)
                    
                    if response.status_code == 200:
                        data = response.json()
                        rate = data['rates'].get(target_currency)
                        if rate:
                            converted_amount = amount_to_convert * rate
                            base_sym = CURRENCY_DATA[base_currency]
                            target_sym = CURRENCY_DATA[target_currency]
                            
                            st.success(f"📈 **Live Rate:** 1 {base_currency} = {rate} {target_currency}")
                            st.info(f"**Result:** {base_sym} {amount_to_convert:,.2f} ➔ **{target_sym} {converted_amount:,.2f}**")
                        else:
                            st.error("Target currency not found in the exchange data.")
                    else:
                        st.error("Failed to fetch exchange rates. Try again later.")
                except Exception as e:
                    st.error(f"Network error: {e}")
