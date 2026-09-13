import streamlit as st
import pandas as pd
import math
from tvDatafeed import TvDatafeed, Interval
from streamlit_autorefresh import st_autorefresh

st.set_page_config(layout="wide", page_title="Dashboard Trading Pro")
st.title("📊 Dashboard Trading Pro")

# Auto-Refresh (60 detik)
st_autorefresh(interval=60000, key="datarefresh")

tv = TvDatafeed()

# ==========================================
# BAGIAN 1: PENGATURAN ANALISA
# ==========================================
st.write("### ⚙️ Pengaturan Analisa")
col1, col2, col3 = st.columns(3)

with col1:
    broker = st.selectbox("Broker:", ["OANDA", "FX_IDC", "BINANCE"], index=0)
with col2:
    # Preset Dropdown untuk MA agar tidak perlu ketik manual
    ma_preset = st.selectbox("Preset MA (Pendek & Panjang):", [
        "20 & 50 (Day Trading/Menengah)",
        "9 & 21 (Scalping/Cepat)",
        "50 & 200 (Long Term)"
    ])
    # Logika untuk membaca angka dari preset yang dipilih
    if ma_preset.startswith("20"):
        ma_pendek, ma_panjang = 20, 50
    elif ma_preset.startswith("9"):
        ma_pendek, ma_panjang = 9, 21
    else:
        ma_pendek, ma_panjang = 50, 200
with col3:
    batas_fvg = st.number_input("Cari FVG (X Candle Terakhir):", min_value=3, max_value=100, value=20)

st.write("---")

# ==========================================
# BAGIAN 2: DAFTAR PAIR & HALAMAN (PAGINATION)
# ==========================================
semua_pairs = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY"]

items_per_page = 10
total_pages = math.ceil(len(semua_pairs) / items_per_page)

page = st.selectbox("Pilih Halaman:", range(1, total_pages + 1))

start_idx = (page - 1) * items_per_page
end_idx = start_idx + items_per_page
displayed_pairs = semua_pairs[start_idx:end_idx]

# ==========================================
# BAGIAN 3: FUNGSI TARIK DATA & RENDER UI
# ==========================================
# Fungsi ini merangkum hitungan FVG lama Anda agar gampang dipanggil di tiap kotak
def get_data_tf(pair_name, tf_code, m_pendek, m_panjang, b_fvg):
    df = tv.get_hist(symbol=pair_name, exchange=broker, interval=tf_code, n_bars=150)
    if df is None or df.empty:
        return None
    
    df['ma_pendek'] = df['close'].rolling(m_pendek).mean()
    df['ma_panjang'] = df['close'].rolling(m_panjang).mean()
    terkini = df.iloc[-1]
    
    waktu = df.index[-1].strftime('%d %b %H:%M')
    harga = terkini['close']
    kondisi_ma = "🟢 Naik" if terkini['ma_pendek'] > terkini['ma_panjang'] else "🔴 Turun"
    
    status_fvg = "⚪ Tidak ada"
    range_teks = "Harga di luar"
    
    for i in range(len(df)-1, len(df)-(b_fvg + 1), -1):
        c1 = df.iloc[i-2]
        c3 = df.iloc[i]
        
        # Bullish FVG
        if c3['low'] > c1['high']:
            b_bawah, b_atas = round(c1['high'], 2), round(c3['low'], 2)
            range_teks = f"{b_bawah} - {b_atas}"
            if b_bawah <= harga <= b_atas:
                status_fvg = "🟢 FVG Naik (Harga Masuk)"
            else:
                status_fvg = "🟢 FVG Naik"
            break 
            
        # Bearish FVG
        elif c3['high'] < c1['low']:
            b_bawah, b_atas = round(c3['high'], 2), round(c1['low'], 2)
            range_teks = f"{b_bawah} - {b_atas}"
            if b_bawah <= harga <= b_atas:
                status_fvg = "🔴 FVG Turun (Harga Masuk)"
            else:
                status_fvg = "🔴 FVG Turun"
            break
            
    return {"waktu": waktu, "harga": harga, "ma": kondisi_ma, "fvg": status_fvg, "range": range_teks}


st.subheader("Hasil Screening Real-time")

daftar_tf_atas = {"W1": Interval.in_weekly, "H4": Interval.in_4_hour, "M15": Interval.in_15_minute}
daftar_tf_bawah = {"D1": Interval.in_daily, "H1": Interval.in_1_hour, "M5": Interval.in_5_minute}

for pair in displayed_pairs:
    with st.container(border=True):
        # Ambil data H1 hanya untuk sekadar menampilkan harga terkini di judul kartu
        dummy_data = get_data_tf(pair, Interval.in_1_hour, ma_pendek, ma_panjang, batas_fvg)
        harga_tampil = dummy_data['harga'] if dummy_data else "Error"
        
        st.markdown(f"### 📈 {pair} &nbsp;&nbsp;|&nbsp;&nbsp; Harga Terkini: `{harga_tampil}`")
        
        # --- BARIS ATAS ---
        cols_atas = st.columns(3)
        for idx, (nama_tf, kode_tf) in enumerate(daftar_tf_atas.items()):
            with cols_atas[idx]:
                data_tf = get_data_tf(pair, kode_tf, ma_pendek, ma_panjang, batas_fvg)
                if data_tf:
                    st.markdown(f"**{nama_tf}**")
                    st.caption(f"⌚ {data_tf['waktu']}")
                    st.markdown(f"MA: {data_tf['ma']}")
                    with st.popover(f"{data_tf['fvg']}"):
                        st.write(f"**Range FVG:**\n\n{data_tf['range']}")
                else:
                    st.write(f"**{nama_tf}**\n\nData gagal dimuat.")
                    
        st.write("") # Spasi pemisah
        
        # --- BARIS BAWAH ---
        cols_bawah = st.columns(3)
        for idx, (nama_tf, kode_tf) in enumerate(daftar_tf_bawah.items()):
            with cols_bawah[idx]:
                data_tf = get_data_tf(pair, kode_tf, ma_pendek, ma_panjang, batas_fvg)
                if data_tf:
                    st.markdown(f"**{nama_tf}**")
                    st.caption(f"⌚ {data_tf['waktu']}")
                    st.markdown(f"MA: {data_tf['ma']}")
                    with st.popover(f"{data_tf['fvg']}"):
                        st.write(f"**Range FVG:**\n\n{data_tf['range']}")
                else:
                    st.write(f"**{nama_tf}**\n\nData gagal dimuat.")
