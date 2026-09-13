import streamlit as st
import pandas as pd
from tvDatafeed import TvDatafeed, Interval
from streamlit_autorefresh import st_autorefresh
from fpdf import FPDF
import datetime

st.set_page_config(layout="wide", page_title="Dashboard Trading Pro")

# --- CSS HACK: MEMAKSA 3 KOLOM DI HP ---
st.markdown("""
<style>
@media (max-width: 640px) {
    /* Memaksa blok baris agar tetap horizontal */
    div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
    }
    /* Membagi setiap kolom menjadi sepertiga layar (33%) */
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        width: 33.33% !important;
        flex: 1 1 33.33% !important;
        min-width: 33.33% !important;
        padding: 0 2px !important;
    }
    /* Memperkecil sedikit ukuran font popover di HP agar muat */
    button[data-testid="baseButton-popover"] {
        font-size: 11px !important;
        padding: 2px 4px !important;
    }
}
</style>
""", unsafe_allow_html=True)

# Auto-Refresh (60 detik)
st_autorefresh(interval=60000, key="datarefresh")

tv = TvDatafeed()

# ==========================================
# BAGIAN 1: PENGATURAN DI SIDEBAR (LACI SAMPING)
# ==========================================
with st.sidebar:
    st.header("⚙️ Pengaturan Analisa")
    
    # 1. Pilihan Broker (Bisa Ketik Sendiri)
    broker_pilihan = st.selectbox("Pilih Broker:", ["OANDA", "FX_IDC", "BINANCE", "PEPPERSTONE", "Ketik Sendiri..."])
    if broker_pilihan == "Ketik Sendiri...":
        broker = st.text_input("Ketik Nama Broker (Contoh: EXNESS):", "OANDA").upper()
    else:
        broker = broker_pilihan
        
    # 2. Pilihan Pair
    daftar_semua_pair = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY"]
    selected_pairs = st.multiselect(
        "Mata Uang (Bisa Ketik/Tambah Sendiri):",
        options=daftar_semua_pair,
        default=["XAUUSD", "EURUSD", "GBPUSD"]
    )
    
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
    
    # 5. FILTERING
    st.write("**Filter Pintar**")
    filter_ma = st.selectbox(
        "Tampilkan Pair berdasarkan kondisi MA di H1:", 
        ["Tampilkan Semua", "Hanya MA Naik", "Hanya MA Turun"]
    )

# ==========================================
# BAGIAN 2: LOGIKA TARIK DATA
# ==========================================
@st.cache_data(ttl=60)
def get_data_tf(pair_name, tf_code, m_pendek, m_panjang, b_fvg, broker_name):
    n_bars_butuh = max(m_panjang + 10, 200) 
    df = tv.get_hist(symbol=pair_name, exchange=broker_name, interval=tf_code, n_bars=n_bars_butuh)
    
    if df is None or df.empty:
        return None
    
    df['ma_pendek'] = df['close'].rolling(m_pendek).mean()
    df['ma_panjang'] = df['close'].rolling(m_panjang).mean()
    terkini = df.iloc[-1]
    
    waktu = df.index[-1].strftime('%d %b %H:%M')
    harga = terkini['close']
    kondisi_ma = "Naik" if terkini['ma_pendek'] > terkini['ma_panjang'] else "Turun"
    
    status_fvg = "Tidak ada"
    range_teks = "Harga di luar"
    
    for i in range(len(df)-1, len(df)-(b_fvg + 1), -1):
        c1 = df.iloc[i-2]
        c3 = df.iloc[i]
        if c3['low'] > c1['high']: # Bullish
            b_bawah, b_atas = round(c1['high'], 2), round(c3['low'], 2)
            range_teks = f"{b_bawah} - {b_atas}"
            status_fvg = "Naik (Harga Masuk)" if b_bawah <= harga <= b_atas else "Naik"
            break 
        elif c3['high'] < c1['low']: # Bearish
            b_bawah, b_atas = round(c3['high'], 2), round(c1['low'], 2)
            range_teks = f"{b_bawah} - {b_atas}"
            status_fvg = "Turun (Harga Masuk)" if b_bawah <= harga <= b_atas else "Turun"
            break
            
    return {"waktu": waktu, "harga": harga, "ma": kondisi_ma, "fvg": status_fvg, "range": range_teks}

# ==========================================
# BAGIAN 3: RENDER UI & FILTERING
# ==========================================
st.title("📊 Dashboard Trading Pro")
st.write("Silakan buka **Laci Samping (Sidebar)** di pojok kiri atas untuk mengubah pengaturan Broker, Mata Uang, dan Preset MA.")

daftar_tf_atas = {"W1": Interval.in_weekly, "H4": Interval.in_4_hour, "M15": Interval.in_15_minute}
daftar_tf_bawah = {"D1": Interval.in_daily, "H1": Interval.in_1_hour, "M5": Interval.in_5_minute}

# Array untuk menampung data yang akan dijadikan PDF
data_untuk_pdf = []

if len(selected_pairs) == 0:
    st.warning("Silakan pilih minimal 1 mata uang (Pair) pada menu pengaturan Sidebar.")
else:
    for pair in selected_pairs:
        # CEK FILTER MA (Acuan H1)
        data_h1_filter = get_data_tf(pair, Interval.in_1_hour, ma_pendek, ma_panjang, batas_fvg, broker)
        if data_h1_filter:
            kondisi_h1 = data_h1_filter['ma']
            if filter_ma == "Hanya MA Naik" and kondisi_h1 == "Turun":
                continue # Lewati / Jangan tampilkan pair ini
            if filter_ma == "Hanya MA Turun" and kondisi_h1 == "Naik":
                continue # Lewati / Jangan tampilkan pair ini
        
        # Bikin Kartu
        with st.container(border=True):
            st.markdown(f"### 📈 {pair} &nbsp;&nbsp;|&nbsp;&nbsp; Harga: `{data_h1_filter['harga'] if data_h1_filter else 'Error'}`")
            
            # Baris Atas
            cols_atas = st.columns(3)
            for idx, (nama_tf, kode_tf) in enumerate(daftar_tf_atas.items()):
                with cols_atas[idx]:
                    data_tf = get_data_tf(pair, kode_tf, ma_pendek, ma_panjang, batas_fvg, broker)
                    if data_tf:
                        st.markdown(f"**{nama_tf}**")
                        st.caption(f"⌚ {data_tf['waktu']}")
                        st.markdown(f"MA: {'🟢' if 'Naik' in data_tf['ma'] else '🔴'} {data_tf['ma']}")
                        
                        # Simpan ke array untuk PDF (Emoji dibuang agar FPDF tidak error)
                        data_untuk_pdf.append({
                            "pair": pair, "tf": nama_tf, "ma": data_tf['ma'], 
                            "fvg": data_tf['fvg'], "range": data_tf['range']
                        })
                        
                        with st.popover(f"FVG: {'🟢' if 'Naik' in data_tf['fvg'] else '🔴' if 'Turun' in data_tf['fvg'] else '⚪'} {data_tf['fvg'].split(' (')[0]}"):
                            st.write(f"**Range FVG:**\n\n{data_tf['range']}")
                    else:
                        st.write(f"**{nama_tf}** Error")
                        
            st.write("") 
            
            # Baris Bawah
            cols_bawah = st.columns(3)
            for idx, (nama_tf, kode_tf) in enumerate(daftar_tf_bawah.items()):
                with cols_bawah[idx]:
                    data_tf = get_data_tf(pair, kode_tf, ma_pendek, ma_panjang, batas_fvg, broker)
                    if data_tf:
                        st.markdown(f"**{nama_tf}**")
                        st.caption(f"⌚ {data_tf['waktu']}")
                        st.markdown(f"MA: {'🟢' if 'Naik' in data_tf['ma'] else '🔴'} {data_tf['ma']}")
                        
                        # Simpan ke array untuk PDF
                        data_untuk_pdf.append({
                            "pair": pair, "tf": nama_tf, "ma": data_tf['ma'], 
                            "fvg": data_tf['fvg'], "range": data_tf['range']
                        })
                        
                        with st.popover(f"FVG: {'🟢' if 'Naik' in data_tf['fvg'] else '🔴' if 'Turun' in data_tf['fvg'] else '⚪'} {data_tf['fvg'].split(' (')[0]}"):
                            st.write(f"**Range FVG:**\n\n{data_tf['range']}")
                    else:
                        st.write(f"**{nama_tf}** Error")

# ==========================================
# BAGIAN 4: EXPORT PDF FORMAT TABEL
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
    pdf.cell(0, 5, "", ln=True) # Spasi
    
    # Header Tabel
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(30, 8, "Pair", border=1, align='C')
    pdf.cell(20, 8, "TF", border=1, align='C')
    pdf.cell(30, 8, "Kondisi MA", border=1, align='C')
    pdf.cell(60, 8, "Status FVG", border=1, align='C')
    pdf.cell(50, 8, "Range FVG", border=1, align='C')
    pdf.ln()
    
    # Isi Data Tabel
    pdf.set_font("Arial", size=9)
    for row in data_list:
        pdf.cell(30, 8, row['pair'], border=1, align='C')
        pdf.cell(20, 8, row['tf'], border=1, align='C')
        pdf.cell(30, 8, row['ma'], border=1, align='C')
        
        # Potong teks FVG yang kepanjangan
        teks_fvg = row['fvg'].split(' (')[0]
        pdf.cell(60, 8, teks_fvg, border=1, align='C')
        pdf.cell(50, 8, row['range'], border=1, align='C')
        pdf.ln()
        
    return pdf.output(dest='S').encode('latin1')

if len(data_untuk_pdf) > 0:
    pdf_bytes = buat_pdf_tabel(data_untuk_pdf)
    st.download_button(
        label="📄 Download Laporan PDF",
        data=pdf_bytes,
        file_name="Laporan_Tabel_Trading.pdf",
        mime="application/pdf"
    )
elif len(selected_pairs) > 0:
    st.info("Tidak ada mata uang yang memenuhi kriteria filter MA Anda.")
