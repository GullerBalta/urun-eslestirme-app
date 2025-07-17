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

# Sütun adlarını normalize et
def normalize_column_names(df):
    df.columns = [col.lower().strip() for col in df.columns]
    rename_map = {}
    for col in df.columns:
        if "kod" in col or "sipariş" in col or "fatura" in col:
            rename_map[col] = "kod"
        elif "ad" in col:
            rename_map[col] = "adi"
    return df.rename(columns=rename_map)

# Kodları standartlaştır
def format_kod(kod, hedef_uzunluk=6):
    if pd.isna(kod):
        return ""
    kod_str = str(kod).strip()
    return kod_str.zfill(hedef_uzunluk) if kod_str.isdigit() else kod_str

# Eşleştirme sonucu etiketi
def eslesme_seviyesi(puan):
    if puan >= 97:
        return "🟢 Mükemmel"
    elif puan >= 90:
        return "🟡 İyi"
    elif puan >= 80:
        return "🟠 Düşük"
    else:
        return "🔴 Eşleşmedi"

# Eşleştirme işlemi
def kod_ad_ile_eslestir(df_fatura, df_siparis):
    eslesen_kayitlar = []
    eslesmeyen_kayitlar = []

    for _, f_row in df_fatura.iterrows():
        kod_f = format_kod(f_row.get("kod", ""))
        ad_f = str(f_row.get("adi", "")).strip().lower()

        en_iyi_oran = 0
        en_iyi_siparis = None

        for _, s_row in df_siparis.iterrows():
            kod_s = format_kod(s_row.get("kod", ""))
            ad_s = str(s_row.get("adi", "")).strip().lower()

            kod_benzerlik = fuzz.ratio(kod_f.lstrip("0"), kod_s.lstrip("0"))  # sıfırları eşleştirmede sayma
            ad_benzerlik = fuzz.ratio(ad_f, ad_s)
            toplam_oran = (w_code * kod_benzerlik) + (w_name * ad_benzerlik)

            if toplam_oran > en_iyi_oran:
                en_iyi_oran = toplam_oran
                en_iyi_siparis = s_row

        if en_iyi_oran >= threshold:
            eslesen_kayitlar.append({
                "fatura_kodu": kod_f,
                "siparis_kodu": en_iyi_siparis["kod"],
                "fatura_adi": f_row.get("adi", ""),
                "siparis_adi": en_iyi_siparis.get("adi", ""),
                "benzerlik": round(en_iyi_oran, 2),
                "durum": eslesme_seviyesi(en_iyi_oran)
            })
        else:
            eslesmeyen_kayitlar.append({
                "fatura_kodu": kod_f,
                "fatura_adi": f_row.get("adi", ""),
                "eslesmeme_orani": round(100 - en_iyi_oran, 2),
                "durum": "🔵 Şüpheli, kontrol edilmeli"
            })

    return pd.DataFrame(eslesen_kayitlar), pd.DataFrame(eslesmeyen_kayitlar)

# Ana işlem
if u_order and u_invoice:
    try:
        df_siparis = pd.read_excel(u_order, dtype=str)
    except:
        df_siparis = pd.read_csv(u_order, dtype=str)

    try:
        df_fatura = pd.read_excel(u_invoice, dtype=str)
    except:
        df_fatura = pd.read_csv(u_invoice, dtype=str)

    # Başlıkları otomatik olarak kod/adi'ye çevir
    df_siparis = normalize_column_names(df_siparis)
    df_fatura = normalize_column_names(df_fatura)

    df_siparis["kod"] = df_siparis["kod"].apply(lambda x: format_kod(x, 6))
    df_fatura["kod"] = df_fatura["kod"].apply(lambda x: format_kod(x, 6))

    df_siparis.fillna("", inplace=True)
    df_fatura.fillna("", inplace=True)

    st.subheader("📦 Sipariş Verileri")
    st.dataframe(df_siparis.head(5000))

    st.subheader("🧾 Fatura Verileri")
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
        st.error("❗ Dosyalarda 'kod' sütunu bulunamadı. Başlıkları kontrol edin.")
else:
    st.info("⬆️ Lütfen sipariş ve fatura dosyalarını yükleyin.")



