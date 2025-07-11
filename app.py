import streamlit as st
import pandas as pd
import re
from rapidfuzz import process, fuzz
from io import BytesIO
from lxml import etree

# Ön işlem: Kod normalizasyonu (harfleri küçük yap, sembol temizle, harf/sayı ayır)
def normalize_code(kod):
    kod = kod.lower().strip()
    kod = re.sub(r"[^a-z0-9]", "", kod)  # sadece harf ve sayı kalsın
    kod = " ".join(re.findall(r"[a-z]+|[0-9]+", kod))  # harf ve sayıyı ayır
    return kod

# Ön işlem: Ürün adını sadeleştir
def normalize_name(name):
    name = name.lower()
    name = re.sub(r"[^a-z0-9çğöşüı\s]", "", name)
    return name.strip()

def extract_items(xml_file):
    tree = etree.parse(xml_file)
    root = tree.getroot()
    records = []

    for tag in ("\u00dcrün_Numarası", "\u00dcrün_Referansı", "Code", "ItemCode"):
        for node in root.findall(f".//{tag}"):
            kod = node.text.strip()
            adi_node = node.getparent().find("Name") or node.getparent().find("\u00dcrün_Adı")
            adi = adi_node.text.strip() if adi_node is not None else ""
            records.append({"kod": normalize_code(kod), "adi": normalize_name(adi)})

    for elem in root.iter():
        txt = (elem.text or "").strip()
        if re.search(r"[A-Za-z0-9]", txt) and len(txt) < 100:
            for kod in re.findall(r"\b[A-Za-z0-9\-\._]{5,20}\b", txt):
                adi = txt.replace(kod, "").strip(" -:;:")
                records.append({"kod": normalize_code(kod), "adi": normalize_name(adi)})

    return pd.DataFrame(records).drop_duplicates(subset=["kod", "adi"])

st.set_page_config(layout="wide")
st.title("📦 Akıllı XML Ürün Kod Eşleştirme Sistemi")

threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
w_code = st.slider("📊 Kod Ağırlığı (%)", 0, 100, 80) / 100.0
w_name = 1 - w_code

u_order = st.file_uploader("📄 Sipariş XML", type="xml")
u_invoice = st.file_uploader("📄 Fatura XML", type="xml")

if u_order and u_invoice:
    df_siparis = extract_items(u_order).head(500)
    df_fatura = extract_items(u_invoice).head(500)

    st.subheader("📦 Sipariş Verisi")
    st.dataframe(df_siparis)
    st.subheader("🗒️ Fatura Verisi")
    st.dataframe(df_fatura)

    with st.spinner("⚡️ Eşleştiriliyor..."):
        results = []
        for _, f_row in df_fatura.iterrows():
            kod_eslesme = process.extractOne(
                f_row["kod"], df_siparis["kod"].tolist(), scorer=fuzz.token_sort_ratio)
            name_eslesme = process.extractOne(
                f_row["adi"], df_siparis["adi"].tolist(), scorer=fuzz.partial_ratio)

            kod_score = kod_eslesme[1] if kod_eslesme else 0
            name_score = name_eslesme[1] if name_eslesme else 0
            total_score = round(w_code * kod_score + w_name * name_score, 1)

            if total_score >= threshold:
                idx = kod_eslesme[2] if kod_score >= name_score else name_eslesme[2]
                match = df_siparis.iloc[idx]
                durum = "EŞLEŞTİ"
            else:
                match = {"kod": "", "adi": ""}
                durum = "EŞLEŞMEDİ"

            results.append({
                "Fatura Kodu": f_row["kod"],
                "Fatura Adı": f_row["adi"],
                "Sipariş Kodu": match["kod"],
                "Sipariş Adı": match["adi"],
                "Eşleşme Oranı (%)": total_score,
                "Durum": durum
            })

        df_results = pd.DataFrame(results)
        st.success("✅ Eşleştirme tamamlandı!")

        st.subheader("✅ Eşleşenler")
        st.dataframe(df_results[df_results["Durum"]=="EŞLEŞTİ"])

        st.subheader("❌ Eşleşmeyenler")
        st.dataframe(df_results[df_results["Durum"]=="EŞLEŞMEDİ"])

        def to_excel(df):
            out = BytesIO()
            with pd.ExcelWriter(out, engine="openpyxl") as writer:
                df.to_excel(writer, index=False)
            return out.getvalue()

        st.download_button("📅 Excel Olarak İndir", to_excel(df_results), file_name="eslestirme_sonuclari.xlsx")





