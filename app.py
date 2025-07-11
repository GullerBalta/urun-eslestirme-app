import streamlit as st
import pandas as pd
import re
from rapidfuzz import process, fuzz
from io import BytesIO
from lxml import etree

st.set_page_config(layout="wide")
st.title("📦 XML Ürün Eşleştirme Sistemi (İlk 500 Kayıt)")

threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
w_code = st.slider("📊 Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
w_name = 1 - w_code

u_order = st.file_uploader("📤 Sipariş XML Dosyasını Yükleyin", type="xml")
u_invoice = st.file_uploader("📤 Fatura XML Dosyasını Yükleyin", type="xml")

def extract_items(xml_file):
    tree = etree.parse(xml_file)
    root = tree.getroot()
    records = []

    for tag in ("Ürün_Numarası", "Ürün_Referansı", "Code", "ItemCode"):
        for node in root.findall(f".//{tag}"):
            kod = node.text.strip()
            adi_node = node.getparent().find("Name") or node.getparent().find("Ürün_Adı")
            adi = adi_node.text.strip() if adi_node is not None else ""
            records.append({"kod": kod, "adi": adi})

    for elem in root.iter():
        txt = (elem.text or "").strip()
        if re.search(r"[A-Za-z0-9]", txt) and len(txt) < 100:
            for kod in re.findall(r"\b[A-Za-z0-9\-\._]{5,20}\b", txt):
                adi = txt.replace(kod, "").strip(" -:;:")
                records.append({"kod": kod, "adi": adi})

    return pd.DataFrame(records).drop_duplicates(subset=["kod", "adi"])

if u_order and u_invoice:
    df_siparis = extract_items(u_order).head(500)
    df_fatura = extract_items(u_invoice).head(500)

    st.subheader("📦 Sipariş Verileri (İlk 500)")
    st.dataframe(df_siparis)

    st.subheader("🧾 Fatura Verileri (İlk 500)")
    st.dataframe(df_fatura)

    with st.spinner("🔄 Eşleştirme işlemi yapılıyor, lütfen bekleyin..."):
        results = []
        siparis_kodlar = df_siparis["kod"].tolist()
        siparis_adlar = df_siparis["adi"].tolist()

        for _, f_row in df_fatura.iterrows():
            kod_eslesme = process.extractOne(f_row["kod"], siparis_kodlar, scorer=fuzz.ratio)
            kod_score, name_score, idx = 0, 0, None

            if kod_eslesme:
                best_kod, kod_score, idx = kod_eslesme

            if f_row["adi"]:
                name_eslesme = process.extractOne(f_row["adi"], siparis_adlar, scorer=fuzz.partial_ratio)
                if name_eslesme:
                    best_name, name_score, idx2 = name_eslesme
                    combined_score = w_code * kod_score + w_name * name_score
                    if combined_score > kod_score:
                        idx = idx2
                        kod_score = combined_score

            if idx is not None and kod_score >= threshold:
                matched = df_siparis.iloc[idx]
                status = "EŞLEŞTİ"
            else:
                matched = {"kod": "", "adi": ""}
                status = "EŞLEŞMEDİ"

            results.append({
                "Fatura Kodu": f_row["kod"],
                "Fatura Adı": f_row["adi"],
                "Sipariş Kodu": matched["kod"],
                "Sipariş Adı": matched["adi"],
                "Eşleşme Oranı (%)": round(kod_score, 1),
                "Durum": status
            })

        df_result = pd.DataFrame(results)

    st.success("✅ Eşleştirme tamamlandı!")
    st.subheader("📊 Eşleştirme Sonuçları")
    st.dataframe(df_result)

    def to_excel(df):
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        return out.getvalue()

    excel_data = to_excel(df_result)
    st.download_button("📥 Excel İndir", data=excel_data, file_name="eslestirme_sonuclari.xlsx")



