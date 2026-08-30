import streamlit as st
import pandas as pd
from tvDatafeed import TvDatafeed, Interval
from streamlit_autorefresh import st_autorefresh

st.set_page_config(layout="wide")
st.title("📊 Dashboard Trading Pro")

# Auto-Refresh (60 detik)
st_autorefresh(interval=60000, key="datarefresh")

tv = TvDatafeed()

st.write("### ⚙️ Pengaturan Analisa")
# Dibagi menjadi 5 kolom agar muat untuk input FVG
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    pair = st.text_input("Pair:", "XAUUSD").upper()
with col2:
    broker = st.text_input("Broker:", "OANDA").upper()
with col3:
    ma_pendek = st.selectbox("MA Pendek:", [7, 20, 30, 50], index=1) 
with col4:
    ma_panjang = st.selectbox("MA Panjang:", [14, 30, 50, 100], index=2) 
with col5:
    # Opsi bagi owner untuk menentukan sendiri batas mundurnya
    batas_fvg = st.number_input("Cari FVG (X Candle Terakhir):", min_value=3, max_value=100, value=20)

daftar_tf = {
    "m5": Interval.in_5_minute,
    "m15": Interval.in_15_minute,
    "h1": Interval.in_1_hour,
    "h4": Interval.in_4_hour,
    "d1": Interval.in_daily,
    "w1": Interval.in_weekly
}

harga_terkini_dict = {}
waktu_cutoff_dict = {}
hasil_ma = {}
hasil_fvg = {}

st.write("---")

for nama_tf, kode_tf in daftar_tf.items():
    # Menarik data lebih banyak untuk cadangan MA panjang + batas FVG maksimal
    df = tv.get_hist(symbol=pair, exchange=broker, interval=kode_tf, n_bars=200)
    
    if df is None or df.empty:
        harga_terkini_dict[nama_tf] = "Error"
        waktu_cutoff_dict[nama_tf] = "-"
        hasil_ma[nama_tf] = "-"
        hasil_fvg[nama_tf] = "-"
        continue
        
    df['ma_pendek'] = df['close'].rolling(ma_pendek).mean()
    df['ma_panjang'] = df['close'].rolling(ma_panjang).mean()
    
    terkini = df.iloc[-1]
    
    harga_terkini_dict[nama_tf] = f"{terkini['close']}"
    waktu_cutoff_dict[nama_tf] = df.index[-1].strftime('%Y-%m-%d %H:%M')

    if terkini['ma_pendek'] > terkini['ma_panjang']:
        hasil_ma[nama_tf] = f"⬆️ Naik"
    else:
        hasil_ma[nama_tf] = f"⬇️ Turun"
        
    # --- LOGIKA FVG DINAMIS SESUAI INPUT OWNER ---
    status_fvg_sementara = "Tdk ada FVG terdekat"
    
    # Looping mundur sesuai angka yang diketik di kotak "batas_fvg"
    for i in range(len(df)-1, len(df)-(batas_fvg + 1), -1):
        c1 = df.iloc[i-2]
        c3 = df.iloc[i]
        
        # Bullish FVG
        if c3['low'] > c1['high']:
            batas_bawah = round(c1['high'], 2)
            batas_atas = round(c3['low'], 2)
            
            if batas_bawah <= terkini['close'] <= batas_atas:
                status_fvg_sementara = f"🟢 FVG Naik ({batas_bawah}-{batas_atas}) | 🎯 HARGA MASUK"
            else:
                status_fvg_sementara = f"🟢 FVG Naik ({batas_bawah}-{batas_atas}) | Harga di luar"
            break 
            
        # Bearish FVG
        elif c3['high'] < c1['low']:
            batas_bawah = round(c3['high'], 2)
            batas_atas = round(c1['low'], 2)
            
            if batas_bawah <= terkini['close'] <= batas_atas:
                status_fvg_sementara = f"🔴 FVG Turun ({batas_bawah}-{batas_atas}) | 🎯 HARGA MASUK"
            else:
                status_fvg_sementara = f"🔴 FVG Turun ({batas_bawah}-{batas_atas}) | Harga di luar"
            break

    hasil_fvg[nama_tf] = status_fvg_sementara

df_tampilan = pd.DataFrame(
    [waktu_cutoff_dict, harga_terkini_dict, hasil_ma, hasil_fvg], 
    index=["Waktu Cut-off (TV)", "Harga Terkini", f"Kondisi MA ({ma_pendek}/{ma_panjang})", "Cek Range FVG"]
)

st.write(f"### Hasil Screening Real-time")
st.dataframe(df_tampilan, use_container_width=True)