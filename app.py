import streamlit as st
import pandas as pd
from tvDatafeed import TvDatafeed, Interval
from streamlit_autorefresh import st_autorefresh
from fpdf import FPDF
import datetime
import time
import json
import os

st.set_page_config(layout="wide", page_title="Dashboard Trading Pro")

# --- CSS: MENGEMBALIKAN TAMPILAN HP KE GULIR BAWAH ---
st.markdown("""
<style>
button[data-testid="baseButton-popover"] {
    width: 100% !important;
}
</style>
""", unsafe_allow_html=True)

# Auto-Refresh (60 detik)
st_autorefresh(interval=60000, key="datarefresh")

# ==========================================
# BAGIAN 1: DATABASE MINI (JSON) AGAR TAHAN REFRESH
# ==========================================
FILE_PENGATURAN = "pengaturan.json"

def muat_pengaturan():
    if os.path.exists(FILE_PENGATURAN):
        try:
            with open(FILE_PENGATURAN, "r") as f:
                return json.load(f)
        except:
            pass
    return {"broker_tersimpan": ["OANDA", "FX_IDC", "BINANCE", "PEPPERSTONE", "IDX", "FXCM"], 
            "pair_tersimpan": ["XAUUSD", "EURUSD", "GBPUSD"]}

def simpan_pengaturan(data):
    with open(FILE_PENGATURAN, "w") as f:
        json.dump(data, f)

data_pengaturan = muat_pengaturan()

# ==========================================
# BAGIAN 2: PENGATURAN KONEKSI TRADINGVIEW
# ==========================================
@st.cache_resource
def get_tv_connection():
    return TvDatafeed()

tv = get_tv_connection()

# ==========================================
# BAGIAN 3: PENGATURAN DI SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ Pengaturan Analisa")
    
    # 1. Pilihan Broker (Tersimpan Permanen)
    pilihan_broker = st.selectbox("Pilih Broker:", data_pengaturan["broker_tersimpan"] + ["+ Tambah Broker Baru..."])
    
    if pilihan_broker == "+ Tambah Broker Baru...":
        broker_baru = st.text_input("Ketik Nama Broker (Lalu Enter):").upper()
        if broker_baru and broker_baru not in data_pengaturan["broker_tersimpan"]:
            data_pengaturan["broker_tersimpan"].append(broker_baru)
            simpan_pengaturan(data_pengaturan) # Simpan ke file JSON
            st.rerun()
        broker = broker_baru if broker_baru else "OANDA"
    else:
        broker = pilihan_broker
        
    st.divider()
        
    # 2. Pilihan Pair (Otomatis Tarik dari Broker)
    st.write(f"**Pilih Mata Uang (Dari {broker})**")
    
    # Menarik daftar populer otomatis dari TradingView sesuai broker yang dipilih
    @st.cache_data(ttl=300) # Cache 5 menit agar cepat
    def ambil_pair_otomatis(nama_broker):
        try:
            hasil = tv.search_symbol(text="", exchange=nama_broker)
            if hasil:
                return [res['symbol'] for res in hasil if 'symbol' in res]
        except:
            pass
        return []
    
    pair_dari_broker = ambil_pair_otomatis(broker)
    
    # Gabungkan pair bawaan (JSON) dengan pair hasil tarikan otomatis agar pilihannya lengkap
    semua_opsi_pair = list(set(data_pengaturan["pair_tersimpan"] + pair_dari_broker))
    semua_opsi_pair.sort() # Urutkan sesuai abjad
    
    selected_pairs = st.multiselect(
        "Pilih (Klik untuk melihat daftar):",
        options=semua_opsi_pair,
        default=[p for p in ["XAUUSD", "EURUSD", "GBPUSD"] if p in semua_opsi_pair]
    )
    
    pair_baru = st.text_input("+ Ketik Manual (Jika tidak ada di daftar):").upper()
    if pair_baru and pair_baru not in data_pengaturan["pair_tersimpan"]:
        data_pengaturan["pair_tersimpan"].append(pair_baru)
        simpan_pengaturan(data_pengaturan) # Simpan permanen
        st.rerun()
    
    st.divider()
    
    # 3. Pengaturan MA
    tipe_ma = st.radio("Pengaturan MA:", ["Gunakan Preset", "Ketik Sendiri"])
    if tipe_ma == "Gunakan Preset":
        ma_preset = st.selectbox("Pilih Preset MA:", ["20 & 50 (Menengah)", "9 & 21 (Cepat)", "50 & 200 (Lambat)"])
        if "20" in ma_preset:
            ma_pendek, ma_panjang = 20, 50
        elif "9" in ma_preset:
            ma_pendek, ma_panjang = 9, 21
        else:
            ma_pendek, ma_panjang = 50, 200
    else:
        c1, c2 = st.columns(2)
        ma_pendek = c1.number_input("MA Pendek:", min_value=1, value=20)
        ma_panjang = c2.number_input("MA Panjang:", min_value=2, value=50)
        
    # 4. Pengaturan FVG
    batas_fvg = st.number_input("Cari FVG (X Candle Terakhir):", min_value=3, max_value=100, value=20)
    
    st.divider()
    
    # 5. FILTERING MA 
    st.write("**Filter Pintar MA**")
    filter_ma = st.selectbox(
        "Filter berdasarkan MA di H1:", 
        ["Tampilkan Semua", "Hanya Tren Naik", "Hanya Tren Turun", "Hanya Momen Crossing Saja!"]
    )

# ==========================================
# BAGIAN 4: LOGIKA TARIK DATA GRAFIK
# ==========================================
@st.cache_data(ttl=60)
def get_data_tf(pair_name, tf_code, m_pendek, m_panjang, b_fvg, broker_name):
    time.sleep(0.3) 
    n_bars_butuh = max(m_panjang + 10, 200) 
    
    try:
        df = tv.get_hist(symbol=pair_name, exchange=broker_name, interval=tf_code, n_bars=n_bars_butuh)
    except:
        return None
        
    if df is None or df.empty:
        return None
    
    df['ma_pendek'] = df['close'].rolling(m_pendek).mean()
    df['ma_panjang'] = df['close'].rolling(m_panjang).mean()
    
    terkini = df.iloc[-1]
    sebelumnya = df.iloc[-2] 
    waktu = df.index[-1].strftime('%d %b %H:%M')
    harga = terkini['close']
    
    if terkini['ma_pendek'] > terkini['ma_panjang']:
        kondisi_ma = "🚀 CROSS NAIK" if sebelumnya['ma_pendek'] <= sebelumnya['ma_panjang'] else "Naik"
    else:
        kondisi_ma = "💥 CROSS TURUN" if sebelumnya['ma_pendek'] >= sebelumnya['ma_panjang'] else "Turun"
    
    status_fvg = "Tidak ada"
    range_teks = "Harga di luar"
    
    for i in range(len(df)-1, len(df)-(b_fvg + 1), -1):
        c1 = df.iloc[i-2]
        c3 = df.iloc[i]
        if c3['low'] > c1['high']: 
            b_bawah, b_atas = round(c1['high'], 2), round(c3['low'], 2)
            range_teks = f"{b_bawah} - {b_atas}"
            status_fvg = "Naik (Harga Masuk)" if b_bawah <= harga <= b_atas else "Naik"
            break 
        elif c3['high'] < c1['low']: 
            b_bawah, b_atas = round(c3['high'], 2), round(c1['low'], 2)
            range_teks = f"{b_bawah} - {b_atas}"
            status_fvg = "Turun (Harga Masuk)" if b_bawah <= harga <= b_atas else "Turun"
            break
            
    return {"waktu": waktu, "harga": harga, "ma": kondisi_ma, "fvg": status_fvg, "range": range_teks}

# ==========================================
# BAGIAN 5: RENDER UI KARTU
# ==========================================
st.title("📊 Dashboard Trading Pro")
st.write("Geser atau buka **Laci Samping (Sidebar)** di pojok kiri atas untuk mengatur alat analisis.")

daftar_tf_atas = {"W1": Interval.in_weekly, "H4": Interval.in_4_hour, "M15": Interval.in_15_minute}
daftar_tf_bawah = {"D1": Interval.in_daily, "H1": Interval.in_1_hour, "M5": Interval.in_5_minute}
data_untuk_pdf = []

if len(selected_pairs) == 0:
    st.warning("Silakan pilih minimal 1 mata uang (Pair) pada menu pengaturan Sidebar.")
else:
    for pair in selected_pairs:
        data_h1_filter = get_data_tf(pair, Interval.in_1_hour, ma_pendek, ma_panjang, batas_fvg, broker)
        if data_h1_filter:
            kondisi_h1 = data_h1_filter['ma']
            if filter_ma == "Hanya Tren Naik" and "Naik" not in kondisi_h1 and "CROSS NAIK" not in kondisi_h1: continue 
            if filter_ma == "Hanya Tren Turun" and "Turun" not in kondisi_h1 and "CROSS TURUN" not in kondisi_h1: continue 
            if filter_ma == "Hanya Momen Crossing Saja!" and "CROSS" not in kondisi_h1: continue 
        
        with st.container(border=True):
            st.markdown(f"### 📈 {pair} &nbsp;&nbsp;|&nbsp;&nbsp; Harga: `{data_h1_filter['harga'] if data_h1_filter else 'Error'}`")
            
            cols_atas = st.columns(3)
            for idx, (nama_tf, kode_tf) in enumerate(daftar_tf_atas.items()):
                with cols_atas[idx]:
                    data_tf = get_data_tf(pair, kode_tf, ma_pendek, ma_panjang, batas_fvg, broker)
                    if data_tf:
                        st.markdown(f"**{nama_tf}**")
                        st.caption(f"⌚ {data_tf['waktu']}")
                        st.markdown(f"MA: **{data_tf['ma']}**" if "CROSS" in data_tf['ma'] else f"MA: {'🟢' if 'Naik' in data_tf['ma'] else '🔴'} {data_tf['ma']}")
                        data_untuk_pdf.append({"pair": pair, "tf": nama_tf, "ma": data_tf['ma'], "fvg": data_tf['fvg'], "range": data_tf['range']})
                        with st.popover(f"FVG: {'🟢' if 'Naik' in data_tf['fvg'] else '🔴' if 'Turun' in data_tf['fvg'] else '⚪'} {data_tf['fvg'].split(' (')[0]}"):
                            st.write(f"**Range FVG:**\n\n{data_tf['range']}")
                    else:
                        st.write(f"**{nama_tf}** Error / Tidak Valid")
                        
            st.write("") 
            
            cols_bawah = st.columns(3)
            for idx, (nama_tf, kode_tf) in enumerate(daftar_tf_bawah.items()):
                with cols_bawah[idx]:
                    data_tf = get_data_tf(pair, kode_tf, ma_pendek, ma_panjang, batas_fvg, broker)
                    if data_tf:
                        st.markdown(f"**{nama_tf}**")
                        st.caption(f"⌚ {data_tf['waktu']}")
                        st.markdown(f"MA: **{data_tf['ma']}**" if "CROSS" in data_tf['ma'] else f"MA: {'🟢' if 'Naik' in data_tf['ma'] else '🔴'} {data_tf['ma']}")
                        data_untuk_pdf.append({"pair": pair, "tf": nama_tf, "ma": data_tf['ma'], "fvg": data_tf['fvg'], "range": data_tf['range']})
                        with st.popover(f"FVG: {'🟢' if 'Naik' in data_tf['fvg'] else '🔴' if 'Turun' in data_tf['fvg'] else '⚪'} {data_tf['fvg'].split(' (')[0]}"):
                            st.write(f"**Range FVG:**\n\n{data_tf['range']}")
                    else:
                        st.write(f"**{nama_tf}** Error / Tidak Valid")

# ==========================================
# BAGIAN 6: EXPORT PDF
# ==========================================
st.write("---")
st.subheader("📥 Download Laporan (Format Tabel)")

def buat_pdf_tabel(data_list):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Laporan Dashboard Trading Pro", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, f"Waktu Cetak: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align='C')
    pdf.cell(0, 5, "", ln=True) 
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(30, 8, "Pair", border=1, align='C')
    pdf.cell(20, 8, "TF", border=1, align='C')
    pdf.cell(40, 8, "Kondisi MA", border=1, align='C')
    pdf.cell(50, 8, "Status FVG", border=1, align='C')
    pdf.cell(50, 8, "Range FVG", border=1, align='C')
    pdf.ln()
    
    pdf.set_font("Arial", size=9)
    for row in data_list:
        pdf.cell(30, 8, row['pair'], border=1, align='C')
        pdf.cell(20, 8, row['tf'], border=1, align='C')
        pdf.cell(40, 8, row['ma'].replace('🚀 ', '').replace('💥 ', ''), border=1, align='C')
        pdf.cell(50, 8, row['fvg'].split(' (')[0], border=1, align='C')
        pdf.cell(50, 8, row['range'], border=1, align='C')
        pdf.ln()
    return pdf.output(dest='S').encode('latin1')

if len(data_untuk_pdf) > 0:
    st.download_button(label="📄 Download Laporan PDF", data=buat_pdf_tabel(data_untuk_pdf), file_name="Laporan_Tabel_Trading.pdf", mime="application/pdf")
