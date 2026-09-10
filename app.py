import io
import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import requests
import plotly.express as px

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
    }
    
    /* Ensure text readability against any background */
    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown, .stText, div[data-testid="metric-container"] label {
        color: #ffffff !important;
        text-shadow: 1px 1px 3px rgba(0,0,0,0.8);
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
    div[data-testid="stMetricValue"] > div {
        color: #00f2fe !important;
        font-weight: 700;
        font-size: clamp(1.1rem, 2.5vw, 1.8rem) !important; 
        text-shadow: 1px 1px 4px rgba(0,0,0,0.9);
        white-space: nowrap !important;
        text-overflow: clip !important; 
        overflow: visible !important;
    }
    div.stButton > button, div[data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%) !important;
        color: white !important;
        text-shadow: none !important;
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
        background-color: rgba(0, 0, 0, 0.4) !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 10px !important;
    }
    div[data-baseweb="input"] input {
        color: white !important;
        background-color: transparent !important;
        padding: 12px !important;
        text-shadow: none !important;
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
        background: rgba(0, 0, 0, 0.6) !important;
        backdrop-filter: blur(16px);
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    [data-testid="stTable"] table { color: white !important; background: transparent !important; width: 100%; text-shadow: none !important; }
    [data-testid="stTable"] th { background-color: rgba(0, 242, 254, 0.2) !important; color: #00f2fe !important; border-bottom: 1px solid rgba(255, 255, 255, 0.3) !important; }
    [data-testid="stTable"] td { background: transparent !important; border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important; }
    [data-testid="stTable"] th:first-child, [data-testid="stTable"] td:first-child { display: none; }
    html, body { overscroll-behavior: none !important; }
    [data-testid="stSidebarNav"], [data-testid="collapsedControl"] { display: none; }
    footer {visibility: hidden;}
    </style>
"""
st.markdown(elegant_css, unsafe_allow_html=True)

# ==========================================
# SESSION STATES & GLOBALS (PERSISTENT LOGIN)
# ==========================================
url_user = st.query_params.get("user")

if 'username' not in st.session_state:
    st.session_state.username = url_user if url_user else None
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'home'

CURRENCY_DATA = {
    "IDR": "Rp", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", 
    "SGD": "S$", "MYR": "RM", "AUD": "A$", "CAD": "C$"
}
KATEGORI_LIST = [
    "Food & Dining", "Groceries", "Transportation", "Housing & Utilities", 
    "Shopping", "Entertainment", "Health & Wellness", "Subscriptions", 
    "Travel", "Education", "Family & Personal", "Other"
]

if 'currency' not in st.session_state:
    st.session_state.currency = 'IDR'
if 'currency_symbol' not in st.session_state:
    st.session_state.currency_symbol = 'Rp'

@st.cache_data(ttl=3600)
def fetch_exchange_rate(base, target):
    if base == target: return 1.0
    try:
        response = requests.get(f"https://api.exchangerate-api.com/v4/latest/{base}")
        if response.status_code == 200:
            return response.json()['rates'].get(target, 1.0)
    except: pass
    return 1.0

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
    
    try: sh = gc.open(MASTER_SHEET_NAME)
    except: st.error("❌ Database file not found. Please contact support."); st.stop()
        
    try: users_sheet = sh.worksheet("Users")
    except:
        users_sheet = sh.add_worksheet(title="Users", rows=1000, cols=2)
        users_sheet.insert_row(["Username", "Password"], 1)

    tab_login, tab_register = st.tabs(["🔑 LOGIN", "📝 REGISTER"])
    
    with tab_login:
        with st.form("form_login"):
            login_user = st.text_input("Username")
            login_pass = st.text_input("Password", type="password")
            submit_login = st.form_submit_button("Sign In", use_container_width=True)
            
            if submit_login:
                users_data = users_sheet.get_all_records()
                if users_data:
                    df_users = pd.DataFrame(users_data)
                    user_match = df_users[(df_users['Username'].astype(str).str.lower() == login_user.lower()) & (df_users['Password'].astype(str) == login_pass)]
                    if not user_match.empty:
                        st.query_params["user"] = login_user.lower()
                        st.session_state.username = login_user.lower()
                        st.session_state.current_page = 'home'
                        st.rerun()
                    else:
                        st.error("❌ Invalid Username or Password. Please try again.")
                else: st.error("No accounts registered yet.")

    with tab_register:
        with st.form("form_register"):
            reg_user = st.text_input("Choose Username")
            reg_pass = st.text_input("Create Password", type="password")
            reg_pass2 = st.text_input("Confirm Password", type="password")
            submit_reg = st.form_submit_button("Create Account", use_container_width=True)
            
            if submit_reg:
                if not reg_user or not reg_pass:
                    st.warning("All fields are required.")
                elif reg_pass != reg_pass2:
                    st.error("❌ Passwords do not match.")
                else:
                    users_data = users_sheet.get_all_records()
                    if users_data:
                        df_users = pd.DataFrame(users_data)
                        if reg_user.lower() in df_users['Username'].astype(str).str.lower().values:
                            st.error("❌ Username is already taken. Please choose another one.")
                            st.stop()
                    
                    users_sheet.append_row([reg_user.lower(), reg_pass])
                    st.success("✅ Account created successfully! Switch to the LOGIN tab to sign in.")
    st.stop()

# ==========================================
# APP INITIALIZATION (POST-LOGIN)
# ==========================================
genai.configure(api_key=st.secrets["gemini_api_key"])
model = genai.GenerativeModel('gemini-1.5-flash')

with st.spinner("Syncing your data..."):
    sh = gc.open(MASTER_SHEET_NAME)
    try: worksheet = sh.worksheet(st.session_state.username)
    except:
        template_sheet = sh.worksheet("Template")
        worksheet = sh.duplicate_sheet(source_sheet_id=template_sheet.id, new_sheet_name=st.session_state.username)

# FETCH DB (IDR based)
total_masuk_str = worksheet.acell('F2').value or '0'
total_keluar_str = worksheet.acell('G2').value or '0'
saldo_str = worksheet.acell('H2').value or '0'
budget_str = worksheet.acell('I2').value or '0' 

raw_income = float(str(total_masuk_str).replace('.', '').replace(',', '')) if total_masuk_str else 0.0
raw_expense = float(str(total_keluar_str).replace('.', '').replace(',', '')) if total_keluar_str else 0.0
raw_balance = float(str(saldo_str).replace('.', '').replace(',', '')) if saldo_str else 0.0
raw_budget = float(str(budget_str).replace('.', '').replace(',', '')) if budget_str else 0.0

rate_to_display = fetch_exchange_rate('IDR', st.session_state.currency)
sym = st.session_state.currency_symbol

disp_income = raw_income * rate_to_display
disp_expense = raw_expense * rate_to_display
disp_balance = raw_balance * rate_to_display
disp_budget = raw_budget * rate_to_display

def format_curr(value):
    return f"{value:,.0f}" if st.session_state.currency in ['IDR', 'JPY'] else f"{value:,.2f}"

# ==========================================
# PAGE 1: HOMESCREEN (MAIN MENU)
# ==========================================
if st.session_state.current_page == 'home':
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.title("💸 Expenses Tracker")
        st.caption(f"👤 Logged in as: **{st.session_state.username}**")
    with col_t2:
        selected_curr = st.selectbox("Currency", options=list(CURRENCY_DATA.keys()), index=list(CURRENCY_DATA.keys()).index(st.session_state.currency))
        if selected_curr != st.session_state.currency:
            st.session_state.currency = selected_curr
            st.session_state.currency_symbol = CURRENCY_DATA[selected_curr]
            st.rerun()

    col1, col2, col3 = st.columns(3)
    col1.metric("Income", f"{sym} {format_curr(disp_income)}")
    col2.metric("Expenses", f"{sym} {format_curr(disp_expense)}")
    col3.metric("Balance", f"{sym} {format_curr(disp_balance)}")

    # ================= BUDGET LIMIT NOTIFICATION =================
    if disp_budget > 0:
        st.write(f"**Monthly Budget Limit:** {sym} {format_curr(disp_budget)}")
        progress = min(disp_expense / disp_budget, 1.0)
        st.progress(progress)
        
        if disp_expense >= disp_budget:
            st.error("🚨 Budget Exceeded! You have spent more than your monthly limit.")
        elif disp_expense >= disp_budget * 0.8:
            st.warning("⚠️ Warning: You've utilized over 80% of your budget. Slow down!")
            
    with st.expander("⚙️ Manage Budget Limit"):
        new_budget = st.number_input(f"Enter Monthly Budget ({sym})", min_value=0.0, step=100.0)
        if st.button("Save Budget"):
            worksheet.update_acell('I2', new_budget * fetch_exchange_rate(st.session_state.currency, 'IDR'))
            st.success("✅ Budget limit updated successfully!")
            st.rerun()

    st.divider()
    st.subheader("📌 Main Menu")
    btn_col1, btn_col2, btn_col3 = st.columns(3)
    with btn_col1:
        if st.button("💰 Add Income", use_container_width=True): st.session_state.current_page = 'income'; st.rerun()
        if st.button("📝 Add Expense", use_container_width=True): st.session_state.current_page = 'manual_expense'; st.rerun()
    with btn_col2:
        if st.button("🤖 Scan Receipt", use_container_width=True): st.session_state.current_page = 'ai_scanner'; st.rerun()
        if st.button("📋 History & Analytics", use_container_width=True): st.session_state.current_page = 'history'; st.rerun()
    with btn_col3:
        if st.button("💱 Exchange Rate", use_container_width=True): st.session_state.current_page = 'exchange'; st.rerun()
        if st.button("🚪 Logout", use_container_width=True):
            st.query_params.clear() 
            st.session_state.username = None
            st.rerun()

# ==========================================
# PAGE 2: ADD INCOME
# ==========================================
elif st.session_state.current_page == 'income':
    if st.button("🏠 Back to Home"): st.session_state.current_page = 'home'; st.rerun()
    st.divider()
    st.title("💰 Add Income")
    
    with st.form("form_income"):
        pemasukan_baru = st.number_input(f"Income Amount ({sym})", min_value=0.0, step=10.0)
        if st.form_submit_button("Save Income", use_container_width=True) and pemasukan_baru > 0:
            worksheet.update_acell('F2', raw_income + (pemasukan_baru * fetch_exchange_rate(st.session_state.currency, 'IDR')))
            st.success("✅ Income added successfully!")
            st.rerun()

# ==========================================
# PAGE 3: ADD EXPENSE (MANUAL)
# ==========================================
elif st.session_state.current_page == 'manual_expense':
    if st.button("🏠 Back to Home"): st.session_state.current_page = 'home'; st.rerun()
    st.title("📝 Add Manual Expense")

    with st.form("form_expense"):
        col_m1, col_m2 = st.columns([3, 1])
        with col_m1:
            nama_barang_manual = st.text_input("Description")
        with col_m2:
            jumlah_manual = st.number_input("Qty", min_value=1, value=1)
            
        col_m3, col_m4 = st.columns(2)
        with col_m3:
            kategori_manual = st.selectbox("Category", KATEGORI_LIST)
        with col_m4:
            nominal_manual = st.number_input(f"Unit Price ({sym})", min_value=0.0, step=5.0)
        
        if st.form_submit_button("Save Expense", use_container_width=True):
            if nama_barang_manual and nominal_manual > 0:
                with st.spinner("Saving..."):
                    total_pengeluaran_idr = (nominal_manual * jumlah_manual) * fetch_exchange_rate(st.session_state.currency, 'IDR')
                    tanggal_manual = (datetime.utcnow() + timedelta(hours=7)).strftime("%d/%m/%Y")
                    baris_baru = len(list(filter(None, worksheet.col_values(1)))) + 1
                    
                    worksheet.update(values=[[tanggal_manual, nama_barang_manual, str(jumlah_manual), total_pengeluaran_idr, kategori_manual]], range_name=f'A{baris_baru}:E{baris_baru}')
                    worksheet.update(values=[[raw_expense + total_pengeluaran_idr, raw_income - (raw_expense + total_pengeluaran_idr)]], range_name='G2:H2')
                    st.success("✅ Expense saved successfully!")
                    st.rerun()
            else:
                st.warning("Please provide a valid description and unit price.")

# ==========================================
# PAGE 4: AI RECEIPT SCANNER
# ==========================================
elif st.session_state.current_page == 'ai_scanner':
    if st.button("🏠 Back to Home"): st.session_state.current_page = 'home'; st.rerun()
    st.title("🤖 AI Receipt Scanner")
    
    with st.form("form_scanner"):
        st.caption("Tip: Provide a custom description if the receipt doesn't explicitly state the item.")
        col_ai1, col_ai2 = st.columns([3, 1])
        with col_ai1: custom_name = st.text_input("Custom Description", placeholder="e.g., Dinner at McD")
        with col_ai2: custom_qty = st.number_input("Qty", min_value=1, value=1)
            
        uploaded_file = st.file_uploader("Upload receipt image", type=['png', 'jpg', 'jpeg'])
        if st.form_submit_button("Scan Receipt", use_container_width=True):
            if uploaded_file:
                with st.spinner("Analyzing receipt..."):
                    try:
                        image = Image.open(uploaded_file)
                        prompt = f"""
                        Analyze this receipt. Extract data into pure JSON (no markdown).
                        1. "tanggal": DD/MM/YYYY.
                        2. "keterangan": Item/Store name.
                        3. "harga_satuan": Price (Number only, assume {st.session_state.currency} if currency is detected).
                        4. "kategori": Must be EXACTLY one of: {", ".join(KATEGORI_LIST)}
                        """
                        response = model.generate_content([prompt, image])
                        data = json.loads(response.text.replace("```json", "").replace("```", "").strip())
                        
                        tanggal = data.get("tanggal", (datetime.utcnow() + timedelta(hours=7)).strftime("%d/%m/%Y"))
                        final_nama = custom_name.strip() if custom_name.strip() != "" else data.get("keterangan", "Expense")
                        kategori_ai = data.get("kategori", "Other")
                        harga_akhir_idr = (float(data.get("harga_satuan", 0)) * custom_qty) * fetch_exchange_rate(st.session_state.currency, 'IDR')
                        
                        if harga_akhir_idr > 0:
                            baris_baru = len(list(filter(None, worksheet.col_values(1)))) + 1
                            worksheet.update(values=[[tanggal, final_nama, str(custom_qty), harga_akhir_idr, kategori_ai]], range_name=f'A{baris_baru}:E{baris_baru}')
                            worksheet.update(values=[[raw_expense + harga_akhir_idr, raw_income - (raw_expense + harga_akhir_idr)]], range_name='G2:H2')
                            st.success(f"✅ Saved: **{final_nama}** ({kategori_ai})")
                            st.rerun()
                        else:
                            st.error("❌ Failed to parse receipt amount. Please ensure the image is clear.")
                    except Exception as e: 
                        st.error("❌ Error analyzing receipt. Please try another image.")
            else:
                st.warning("⚠️ Please upload a receipt image first.")

# ==========================================
# PAGE 5: TRANSACTION HISTORY & ANALYTICS
# ==========================================
elif st.session_state.current_page == 'history':
    if st.button("🏠 Back to Home"): st.session_state.current_page = 'home'; st.rerun()
    st.divider()
    st.title("📋 History & Analytics")
    
    semua_data = worksheet.get_all_values()
    if len(semua_data) > 1:
        records = []
        for row in semua_data[1:]:
            clean_row = row[:5]
            clean_row += ['Other'] * (5 - len(clean_row))
            if clean_row[4] == '':
                clean_row[4] = 'Other'
            records.append(clean_row)
            
        df = pd.DataFrame(records, columns=['Tanggal', 'Keterangan', 'Jumlah', 'Pengeluaran', 'Kategori'])
        
        # Simpan nomor baris asli untuk sinkronisasi dengan Google Sheets
        df['Sheet_Row'] = df.index + 2 
        
        df = df[df['Tanggal'].astype(bool) & (df['Tanggal'] != '')]
        
        df['Total Num'] = pd.to_numeric(df['Pengeluaran'].astype(str).str.replace('.', '', regex=False).str.replace(',', '', regex=False), errors='coerce').fillna(0) * rate_to_display
        df['Total Expense'] = df['Total Num'].apply(lambda x: f"{sym} {format_curr(x)}")
        
        # --- TABLE & DATE FILTER ---
        st.subheader("📄 Transaction List")
        filter_date = st.date_input("🗓️ Filter by Date", value=None)
        
        df_tampil = df[['Sheet_Row', 'Tanggal', 'Keterangan', 'Jumlah', 'Kategori', 'Total Expense']].copy()
        if filter_date:
            df_tampil = df_tampil[df_tampil['Tanggal'] == filter_date.strftime("%d/%m/%Y")]
        
        st.caption("💡 *Tip: Click on any Category cell below to change it, then press Save.*")
        
        # TABEL INTERAKTIF DENGAN DROPDOWN
        edited_df = st.data_editor(
            df_tampil,
            column_config={
                "Sheet_Row": None, # Sembunyikan kolom sistem ini dari layar
                "Tanggal": st.column_config.TextColumn("Date", disabled=True),
                "Keterangan": st.column_config.TextColumn("Description", disabled=True),
                "Jumlah": st.column_config.TextColumn("Qty", disabled=True),
                "Total Expense": st.column_config.TextColumn(f"Total ({sym})", disabled=True),
                "Kategori": st.column_config.SelectboxColumn(
                    "Category",
                    options=KATEGORI_LIST,
                    required=True
                )
            },
            hide_index=True,
            use_container_width=True,
            key="history_editor"
        )
        
        # TOMBOL SIMPAN PERUBAHAN KE GOOGLE SHEETS
        if st.button("💾 Save Category Changes", use_container_width=True):
            with st.spinner("Saving changes to database..."):
                changes_made = False
                # Cek baris mana saja yang kategorinya diubah oleh user
                for idx in edited_df.index:
                    old_cat = df_tampil.loc[idx, 'Kategori']
                    new_cat = edited_df.loc[idx, 'Kategori']
                    if old_cat != new_cat:
                        sheet_row = edited_df.loc[idx, 'Sheet_Row']
                        worksheet.update_acell(f'E{sheet_row}', new_cat)
                        changes_made = True
                
                if changes_made:
                    st.success("✅ Categories updated successfully!")
                    st.rerun()
                else:
                    st.info("No changes detected.")
        
        st.divider()
        
        # DOWNLOAD EXCEL BUTTON
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            # Hapus kolom Sheet_Row biar nggak ikut ke-download
            df_tampil.drop(columns=['Sheet_Row']).to_excel(writer, index=False, sheet_name='Transactions')
        
        st.download_button(
            label="📥 Export to Excel",
            data=buffer.getvalue(),
            file_name="expenses_history.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # --- PIE CHART (CATEGORY PERCENTAGE) ---
        st.divider()
        st.subheader("📊 Expenses by Category")
        df_pie = df.groupby('Kategori')['Total Num'].sum().reset_index()
        
        if not df_pie.empty and df_pie['Total Num'].sum() > 0:
            fig = px.pie(df_pie, values='Total Num', names='Kategori', hole=0.4, color_discrete_sequence=px.colors.sequential.Tealgrn)
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='white'))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough data available to generate a chart.")
            
    else: st.info("No transaction records found.")

# ==========================================
# PAGE 6: CURRENCY EXCHANGE RATE
# ==========================================
elif st.session_state.current_page == 'exchange':
    if st.button("🏠 Back to Home"): st.session_state.current_page = 'home'; st.rerun()
    st.divider()
    st.title("💱 Exchange Rate")
    
    with st.form("form_exchange"):
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1: base_curr = st.selectbox("From", options=list(CURRENCY_DATA.keys()))
        with col_ex2: target_curr = st.selectbox("To", options=list(CURRENCY_DATA.keys()), index=1)
        amt = st.number_input("Amount", min_value=0.0, value=1.0)
        
        if st.form_submit_button("Convert Currency", use_container_width=True):
            with st.spinner("Fetching live rates..."):
                rate = fetch_exchange_rate(base_curr, target_curr)
                if rate:
                    st.success(f"📈 1 {base_curr} = {rate} {target_curr}")
                    st.info(f"**Result:** {CURRENCY_DATA[base_curr]} {amt:,.2f} ➔ **{CURRENCY_DATA[target_curr]} {(amt * rate):,.2f}**")
                else:
                    st.error("❌ Failed to fetch current exchange rates.")
