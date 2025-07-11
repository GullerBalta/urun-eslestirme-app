import streamlit as st
import pandas as pd
import re
from rapidfuzz import fuzz
from io import BytesIO
from lxml import etree

st.set_page_config(page_title="XML Ürün Eşleştirme", layout="wide")
st.title("📦 XML Ürün Eşleştirme Sistemi")

uploaded_order = st.file_uploader("📤 Sipariş XML Dosyasını Yükle", type=["xml"])
uploaded_invoice = st.file_uploader("📤 Fatura XML Dosyasını Yükle", type=["xml"])
threshold = st.slider("🔍 Benzerlik Eşik Değeri (%)", 80, 100, 95)

def extract_codes_and_names(xml_file):
    tree = etree.parse(xml_file)
    root = tree.getroot()
    kayitlar = []
    
    for eleman in root.iter():
        if eleman.text:
            metin = eleman.text.strip()
            kodlar = re.findall(r'\b[A-Za-z0-9\-\.]{5,15}\b', metin)
            for kod in kodlar:
                kayitlar.append({
                    "urun_kodu": kod,
                    "urun_adi": metin
                })
        if len(kayitlar) >= 1000:  # İlk 1000 kayıtla sınırla
            break
    return pd.DataFrame(kayitlar)

if uploaded_order and uploaded_invoice:
    df_siparis = extract_codes_and_names(uploaded_order)
    df_fatura = extract_codes_and_names(uploaded_invoice)

    st.subheader("📦 Sipariş Verisi (İlk 1000 kayıt)")
    st.dataframe(df_siparis)

    st.subheader("🧾 Fatura Verisi (İlk 1000 kayıt)")
    st.dataframe(df_fatura)

    eslesen = []
    eslesmeyen = []

    st.info("🔄 Eşleştirme Başladı...")

    for _, f_row in df_fatura.iterrows():
        best_match = None
        best_score = 0

        for _, s_row in df_siparis.iterrows():
            score = fuzz.ratio(str(f_row["urun_kodu"]), str(s_row["urun_kodu"]))
            if score > best_score:
                best_score = score
                best_match = s_row

        if best_score >= threshold:
            eslesen.append({
                "fatura_kodu": f_row["urun_kodu"],
                "fatura_adi": f_row["urun_adi"],
                "siparis_kodu": best_match["urun_kodu"],
                "siparis_adi": best_match["urun_adi"],
                "eşleşme_oranı (%)": round(best_score, 1),
                "durum": "EŞLEŞTİ"
            })
        else:
            eslesmeyen.append({
                "fatura_kodu": f_row["urun_kodu"],
                "fatura_adi": f_row["urun_adi"],
                "siparis_kodu": "",
                "siparis_adi": "",
                "eşleşme_oranı (%)": round(best_score, 1),
                "durum": "EŞLEŞMEDİ"
            })

    st.subheader("📊 Eşleştirme Sonuçları (Tablo Halinde)")
    df_sonuc = pd.DataFrame(eslesen + eslesmeyen)
    st.dataframe(df_sonuc)

    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Eslestirme', index=False)
        return output.getvalue()

    excel_data = to_excel(df_sonuc)
    st.download_button("📥 Excel Olarak İndir", excel_data, file_name="eslestirme_sonuclari.xlsx")

