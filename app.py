import streamlit as st
import pandas as pd
import re
from rapidfuzz import fuzz
from io import BytesIO

st.title("📦 XML Ürün Eşleştirme Sistemi")

uploaded_order = st.file_uploader("📤 Sipariş XML Dosyasını Yükle", type=["xml"])
uploaded_invoice = st.file_uploader("📤 Fatura XML Dosyasını Yükle", type=["xml"])

def extract_codes_from_xml(xml_file):
    from lxml import etree
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
                    "tam_metin": metin
                })
    return pd.DataFrame(kayitlar)

if uploaded_order and uploaded_invoice:
    df_siparis = extract_codes_from_xml(uploaded_order)
    df_fatura = extract_codes_from_xml(uploaded_invoice)
    st.subheader("📦 Sipariş Dosyasından Çıkan Veriler")
    st.write(df_siparis)

    st.subheader("🧾 Fatura Dosyasından Çıkan Veriler")
    st.write(df_fatura)
    eslesen = []
    eslesmeyen = []

    for _, f_row in df_fatura.iterrows():
        best_match = None
        best_score = 0

        for _, s_row in df_siparis.iterrows():
            score = fuzz.ratio(f_row["urun_kodu"], s_row["urun_kodu"])
            if score > best_score:
                best_score = score
                best_match = s_row

        if best_score >= 95:
            eslesen.append({
                "fatura_kodu": f_row["urun_kodu"],
                "siparis_kodu": best_match["urun_kodu"],
                "benzerlik": best_score,
                "durum": "EŞLEŞTİ"
            })
        else:
            eslesmeyen.append({
                "fatura_kodu": f_row["urun_kodu"],
                "benzerlik": best_score,
                "durum": "EŞLEŞMEDİ"
            })

    st.subheader("✅ Eşleşen Kodlar")
    df_eslesen = pd.DataFrame(eslesen)
    st.dataframe(df_eslesen)

    st.subheader("❌ Eşleşmeyen Kodlar")
    df_eslesmeyen = pd.DataFrame(eslesmeyen)
    st.dataframe(df_eslesmeyen)

    # Excel çıktısı
    def to_excel(df1, df2):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df1.to_excel(writer, sheet_name='Eslesen', index=False)
            df2.to_excel(writer, sheet_name='Eslesmeyen', index=False)
        return output.getvalue()

    excel_data = to_excel(df_eslesen, df_eslesmeyen)
    st.download_button("📥 Excel Olarak İndir", excel_data, file_name="eslestirme_sonuclari.xlsx")


    eslesen = []
    eslesmeyen = []

    for _, f_row in df_fatura.iterrows():
        best_match = None
        best_score = 0

        for _, s_row in df_siparis.iterrows():
            score = fuzz.ratio(f_row["urun_kodu"], s_row["urun_kodu"])
            if score > best_score:
                best_score = score
                best_match = s_row

        if best_score >= 95:
            eslesen.append({
                "fatura_kodu": f_row["urun_kodu"],
                "siparis_kodu": best_match["urun_kodu"],
                "benzerlik": best_score,
                "durum": "EŞLEŞTİ"
            })
        else:
            eslesmeyen.append({
                "fatura_kodu": f_row["urun_kodu"],
                "benzerlik": best_score,
                "durum": "EŞLEŞMEDİ"
            })

    st.subheader("✅ Eşleşen Kodlar")
    df_eslesen = pd.DataFrame(eslesen)
    st.dataframe(df_eslesen)

    st.subheader("❌ Eşleşmeyen Kodlar")
    df_eslesmeyen = pd.DataFrame(eslesmeyen)
    st.dataframe(df_eslesmeyen)

    def to_excel(df1, df2):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df1.to_excel(writer, sheet_name='Eslesen', index=False)
            df2.to_excel(writer, sheet_name='Eslesmeyen', index=False)
        return output.getvalue()

    excel_data = to_excel(df_eslesen, df_eslesmeyen)
    st.download_button("📥 Excel Olarak İndir", excel_data, file_name="eslestirme_sonuclari.xlsx")

