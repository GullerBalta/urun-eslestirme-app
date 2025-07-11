import streamlit as st
import pandas as pd
import re
from rapidfuzz import fuzz
from io import BytesIO

st.title("📦 XML Ürün Eşleştirme Sistemi")

uploaded_order = st.file_uploader("📤 Sipariş XML Dosyasını Yükle", type=["xml"])
uploaded_invoice = st.file_uploader("📤 Fatura XML Dosyasını Yükle", type=["xml"])
esik_deger = st.slider("🎯 Eşik Benzerlik Skoru (%)", min_value=50, max_value=100, value=90)

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
                    "urun_adi": metin  # ürün adı aynı metin içinde olabilir
                })
    return pd.DataFrame(kayitlar).drop_duplicates()

if uploaded_order and uploaded_invoice:
    df_siparis = extract_codes_from_xml(uploaded_order)
    df_fatura = extract_codes_from_xml(uploaded_invoice)

    st.subheader("📦 Sipariş Dosyasından Çıkan Veriler")
    st.dataframe(df_siparis)

    st.subheader("🧾 Fatura Dosyasından Çıkan Veriler")
    st.dataframe(df_fatura)

    st.info("🔍 Eşleştirme Başladı...")

    eslesen = []
    eslesmeyen = []

    for _, f_row in df_fatura.iterrows():
        best_match = None
        best_score = 0
        best_kod_skor = 0
        best_ad_skor = 0

        for _, s_row in df_siparis.iterrows():
            kod_skor = fuzz.ratio(f_row["urun_kodu"], s_row["urun_kodu"])
            ad_skor = fuzz.ratio(f_row["urun_adi"], s_row["urun_adi"])
            skor = 0.7 * kod_skor + 0.3 * ad_skor

            if skor > best_score:
                best_score = skor
                best_kod_skor = kod_skor
                best_ad_skor = ad_skor
                best_match = s_row

        if best_score >= esik_deger:
            eslesen.append({
                "fatura_kodu": f_row["urun_kodu"],
                "siparis_kodu": best_match["urun_kodu"],
                "kod_skor": best_kod_skor,
                "ad_skor": best_ad_skor,
                "toplam_skor": round(best_score, 2),
                "durum": "EŞLEŞTİ"
            })
            st.success(f"✔ EŞLEŞTİ: {f_row['urun_kodu']} ↔ {best_match['urun_kodu']} | Skor: {round(best_score, 1)}")
        else:
            eslesmeyen.append({
                "fatura_kodu": f_row["urun_kodu"],
                "urun_adi": f_row["urun_adi"],
                "toplam_skor": round(best_score, 2),
                "durum": "EŞLEŞMEDİ"
            })

    df_eslesen = pd.DataFrame(eslesen)
    df_eslesmeyen = pd.DataFrame(eslesmeyen)

    st.subheader("✅ Eşleşen Kayıtlar")
    st.dataframe(df_eslesen)

    st.subheader("❌ Eşleşmeyen Kayıtlar")
    st.dataframe(df_eslesmeyen)

    def to_excel(df1, df2):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df1.to_excel(writer, sheet_name='Eslesen', index=False)
            df2.to_excel(writer, sheet_name='Eslesmeyen', index=False)
        return output.getvalue()

    excel_data = to_excel(df_eslesen, df_eslesmeyen)
    st.download_button("📥 Excel Olarak İnd_


