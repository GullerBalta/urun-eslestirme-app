import streamlit as st
import pandas as pd
import re
from rapidfuzz import fuzz
from io import BytesIO

st.set_page_config(layout="wide")
st.title("📦 Akıllı Sipariş | Fatura Karşılaştırma ve Tedarikçi Ekleme Sistemi")

threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
w_code = st.slider("📊 Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
w_name = 1 - w_code

u_order = st.file_uploader("📤 Sipariş Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])
u_invoice = st.file_uploader("📤 Fatura Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])

# Baştaki sıfırları eşleştirmede sil, görüntüde tut
def temizle_kod(kod):
    if pd.isna(kod):
        return ""
    kod = str(kod).strip()
    return re.sub(r"^0+", "", kod)

# Eşleşme seviyesi ifadesi
def eslesme_seviyesi(puan):
    if puan >= 97:
        return "🟢 Mükemmel"
    elif puan >= 90:
        return "🟡 İyi"
    elif puan >= 80:
        return "🟠 Düşük"
    else:
        return "🔴 Eşleşmedi"

# Başlıkları normalize et: "ürün kodu" → "kod", "Ürün Adı" → "adi"
def normalize_column_names(df):
    original_columns = df.columns.tolist()
    df.columns = [col.strip().lower() for col in df.columns]
    rename_map = {}
    for col in df.columns:
        if "kod" in col:
            rename_map[col] = "kod"
        elif "ad" in col:
            rename_map[col] = "adi"
    df = df.rename(columns=rename_map)
    return df, original_columns

# Eşleştirme fonksiyonu
def kod_ad_ile_eslestir(df_fatura, df_siparis):
    eslesen_kayitlar = []
    eslesmeyen_kayitlar = []

    for _, f_row in df_fatura.iterrows():
        kod_f = str(f_row.get("kod", "")).strip()
        ad_f = str(f_row.get("adi", "")).strip()
        kod_f_clean = temizle_kod(kod_f)
        ad_f_clean = ad_f.lower()

        en_iyi_oran = 0
        en_iyi_siparis = None

        for _, s_row in df_siparis.iterrows():
            kod_s = str(s_row.get("kod", "")).strip()
            ad_s = str(s_row.get("adi", "")).strip()
            kod_s_clean = temizle_kod(kod_s)
            ad_s_clean = ad_s.lower()

            kod_benzerlik = fuzz.ratio(kod_f_clean, kod_s_clean)
            ad_benzerlik = fuzz.ratio(ad_f_clean, ad_s_clean)
            toplam_oran = (w_code * kod_benzerlik) + (w_name * ad_benzerlik)

            if toplam_oran > en_iyi_oran:
                en_iyi_oran = toplam_oran
                en_iyi_siparis = s_row

        if en_iyi_oran >= threshold:
            eslesen_kayitlar.append({
                "fatura_kodu": kod_f,
                "siparis_kodu": en_iyi_siparis["kod"],
                "fatura_adi": ad_f,
                "siparis_adi": en_iyi_siparis["adi"],
                "benzerlik": round(en_iyi_oran, 2),
                "durum": eslesme_seviyesi(en_iyi_oran)
            })
        else:
            eslesmeyen_kayitlar.append({
                "fatura_kodu": kod_f,
                "fatura_adi": ad_f,
                "eslesmeme_orani": round(100 - en_iyi_oran, 2),
                "durum": "🔵 Şüpheli, kontrol edilmeli"
            })

    return pd.DataFrame(eslesen_kayitlar), pd.DataFrame(eslesmeyen_kayitlar)

if u_order and u_invoice:
    try:
        df_siparis = pd.read_excel(u_order, dtype=str)
    except:
        df_siparis = pd.read_csv(u_order, dtype=str)

    try:
        df_fatura = pd.read_excel(u_invoice, dtype=str)
    except:
        df_fatura = pd.read_csv(u_invoice, dtype=str)

    # Orijinal sütun adlarını göster
    st.write("📋 Sipariş Dosyası Orijinal Sütun Başlıkları:")
    st.write(df_siparis.columns.tolist())
    st.write("📋 Fatura Dosyası Orijinal Sütun Başlıkları:")
    st.write(df_fatura.columns.tolist())

    # Normalize et
    df_siparis, _ = normalize_column_names(df_siparis)
    df_fatura, _ = normalize_column_names(df_fatura)

    df_siparis.fillna("", inplace=True)
    df_fatura.fillna("", inplace=True)

    st.subheader("📦 Sipariş Verileri (İlk 5000)")
    st.dataframe(df_siparis.head(5000))

    st.subheader("🧾 Fatura Verileri (İlk 5000)")
    st.dataframe(df_fatura.head(5000))

    if "kod" in df_siparis.columns and "kod" in df_fatura.columns:
        df_eslesen, df_eslesmeyen = kod_ad_ile_eslestir(df_fatura, df_siparis)

        st.subheader(f"✅ Eşleşen Kayıtlar: {len(df_eslesen)}")
        st.dataframe(df_eslesen)

        st.subheader(f"❌ Eşleşmeyen Kayıtlar: {len(df_eslesmeyen)}")
        st.dataframe(df_eslesmeyen)

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_eslesen.to_excel(writer, sheet_name="Eslesen", index=False)
            df_eslesmeyen.to_excel(writer, sheet_name="Eslesmeyen", index=False)
        st.download_button("📥 Excel İndir", buffer.getvalue(), file_name="eslesme_sonuclari.xlsx")
    else:
        st.error("❗ Yüklenen dosyalarda 'kod' sütunu eksik. Lütfen sütun adlarını kontrol edin.")
else:
    st.info("⬆️ Lütfen sipariş ve fatura dosyalarını yükleyin.")



