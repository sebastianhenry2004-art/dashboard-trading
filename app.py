import streamlit as st
import pandas as pd
from tvDatafeed import TvDatafeed, Interval
from streamlit_autorefresh import st_autorefresh
from fpdf import FPDF
import datetime

st.set_page_config(layout="wide", page_title="Dashboard Trading Pro")

# --- CSS HACK UNTUK TAMPILAN HP ---
# Memaksa kolom timeframe agar tetap ke samping (horizontal) di layar HP
st.markdown("""
<style>
@media (max-width: 600px) {
    div[data-testid="column"] {
        width: 32% !important;
        flex: 1 1 32% !important;
        min-width: 32% !important;
        padding: 0 2px !important;
    }
}
</style>
""", unsafe_allow_html=True)

st.title("📊 Dashboard Trading Pro")

# Auto-Refresh (60 detik)
st_autorefresh(interval=60000, key="datarefresh")

tv = TvDatafeed()

# ==========================================
# BAGIAN 1: PENGATURAN AWAL & TAMPILAN
# ==========================================
st.write("### ⚙️ Pengaturan Analisa")

col_set1, col_set2 = st.columns(2)

with col_set1:
    broker = st.selectbox("Pilih Broker:", ["OANDA", "FX_IDC", "BINANCE", "PEPPERSTONE"])
    
    # Fitur Ketik dan Suggest Mata Uang
    daftar_semua_pair = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY"]
    selected_pairs = st.multiselect(
        "Pilih Mata Uang yang mau ditampilkan (Bisa ketik sendiri):",
        options=daftar_semua_pair,
        default=["XAUUSD", "EURUSD"] # Tampilan awal saat baru dibuka
    )

with col_set2:
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
        
    batas_fvg = st.number_input("Cari FVG (X Candle Terakhir):", min_value=3, max_value=100, value=20)

st.divider()

# ==========================================
# BAGIAN 2: LOGIKA TARIK DATA
# ==========================================
@st.cache_data(ttl=60) # Cache agar tidak kena limit dari TradingView
def get_data_tf(pair_name, tf_code, m_pendek, m_panjang, b_fvg, broker_name):
    # n_bars dibuat lebih besar dari MA terpanjang agar indikator akurat
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
        
        # Bullish FVG
        if c3['low'] > c1['high']:
            b_bawah, b_atas = round(c1['high'], 2), round(c3['low'], 2)
            range_teks = f"{b_bawah} - {b_atas}"
            if b_bawah <= harga <= b_atas:
                status_fvg = "Naik (Harga Masuk)"
            else:
                status_fvg = "Naik"
            break 
            
        # Bearish FVG
        elif c3['high'] < c1['low']:
            b_bawah, b_atas = round(c3['high'], 2), round(c1['low'], 2)
            range_teks = f"{b_bawah} - {b_atas}"
            if b_bawah <= harga <= b_atas:
                status_fvg = "Turun (Harga Masuk)"
            else:
                status_fvg = "Turun"
            break
            
    return {"waktu": waktu, "harga": harga, "ma": kondisi_ma, "fvg": status_fvg, "range": range_teks}

# ==========================================
# BAGIAN 3: RENDER UI & KARTU
# ==========================================
daftar_tf_atas = {"W1": Interval.in_weekly, "H4": Interval.in_4_hour, "M15": Interval.in_15_minute}
daftar_tf_bawah = {"D1": Interval.in_daily, "H1": Interval.in_1_hour, "M5": Interval.in_5_minute}

st.subheader("Hasil Screening Real-time")

# Array untuk menyimpan teks PDF nantinya
pdf_data_strings = []

if len(selected_pairs) == 0:
    st.warning("Silakan pilih minimal 1 mata uang (Pair) pada menu pengaturan di atas.")
else:
    for pair in selected_pairs:
        with st.container(border=True):
            dummy_data = get_data_tf(pair, Interval.in_1_hour, ma_pendek, ma_panjang, batas_fvg, broker)
            harga_tampil = dummy_data['harga'] if dummy_data else "Error"
            
            st.markdown(f"### 📈 {pair} &nbsp;&nbsp;|&nbsp;&nbsp; Harga: `{harga_tampil}`")
            pdf_data_strings.append(f"Pair: {pair} | Harga: {harga_tampil}")
            
            cols_atas = st.columns(3)
            for idx, (nama_tf, kode_tf) in enumerate(daftar_tf_atas.items()):
                with cols_atas[idx]:
                    data_tf = get_data_tf(pair, kode_tf, ma_pendek, ma_panjang, batas_fvg, broker)
                    if data_tf:
                        st.markdown(f"**{nama_tf}**")
                        st.caption(f"⌚ {data_tf['waktu']}")
                        st.markdown(f"MA: {'🟢' if 'Naik' in data_tf['ma'] else '🔴'} {data_tf['ma']}")
                        
                        pdf_data_strings.append(f" - {nama_tf}: MA {data_tf['ma']}, FVG {data_tf['fvg']}")
                        
                        with st.popover(f"FVG: {'🟢' if 'Naik' in data_tf['fvg'] else '🔴' if 'Turun' in data_tf['fvg'] else '⚪'} {data_tf['fvg'].split(' (')[0]}"):
                            st.write(f"**Range FVG:**\n\n{data_tf['range']}\n\n**Detail:** {data_tf['fvg']}")
                    else:
                        st.write(f"**{nama_tf}**\n\nData error")
                        
            st.write("") 
            
            cols_bawah = st.columns(3)
            for idx, (nama_tf, kode_tf) in enumerate(daftar_tf_bawah.items()):
                with cols_bawah[idx]:
                    data_tf = get_data_tf(pair, kode_tf, ma_pendek, ma_panjang, batas_fvg, broker)
                    if data_tf:
                        st.markdown(f"**{nama_tf}**")
                        st.caption(f"⌚ {data_tf['waktu']}")
                        st.markdown(f"MA: {'🟢' if 'Naik' in data_tf['ma'] else '🔴'} {data_tf['ma']}")
                        
                        pdf_data_strings.append(f" - {nama_tf}: MA {data_tf['ma']}, FVG {data_tf['fvg']}")
                        
                        with st.popover(f"FVG: {'🟢' if 'Naik' in data_tf['fvg'] else '🔴' if 'Turun' in data_tf['fvg'] else '⚪'} {data_tf['fvg'].split(' (')[0]}"):
                            st.write(f"**Range FVG:**\n\n{data_tf['range']}\n\n**Detail:** {data_tf['fvg']}")
                    else:
                        st.write(f"**{nama_tf}**\n\nData error")
            
            pdf_data_strings.append("") # Spasi di PDF

# ==========================================
# BAGIAN 4: EXPORT KE PDF
# ==========================================
st.write("---")
st.subheader("📥 Download Laporan")

def buat_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Laporan Dashboard Trading Pro", ln=True, align='C')
    pdf.cell(200, 10, txt=f"Waktu Cetak: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align='C')
    pdf.cell(200, 10, txt="-"*50, ln=True, align='C')
    
    for baris in pdf_data_strings:
        pdf.cell(200, 8, txt=baris, ln=True)
        
    return pdf.output(dest='S').encode('latin1')

# Tombol Download
if len(selected_pairs) > 0:
    pdf_bytes = buat_pdf()
    st.download_button(
        label="📄 Download Laporan PDF",
        data=pdf_bytes,
        file_name="Laporan_Trading.pdf",
        mime="application/pdf"
    )
