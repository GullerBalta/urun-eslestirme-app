import streamlit as st
import pandas as pd
import re
from rapidfuzz import process, fuzz
from io import BytesIO
from lxml import etree

st.set_page_config(layout="wide")
st.title("📦 Genel XML Ürün Eşleştirme Sistemi")

# Kullanıcı eşiği ve ağırlıkları belirlesin
threshold = st.slider("Benzerlik Eşik Değeri (%)", 50, 100, 90)
w_code  = st.slider("Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
w_name  = 1 - w_code

u_order   = st.file_uploader("Sipariş XML", type="xml")
u_invoice = st.file_uploader("Fatura XML", type="xml")

def extract_items(xml_file):
    tree = etree.parse(xml_file)
    root = tree.getroot()
    records = []
    # Öncelikli etiketler
    for tag in ("Ürün_Numarası","Ürün_Referansı","Code","ItemCode"):
        for node in root.findall(f".//{tag}"):
            kod = node.text.strip()
            adi_node = node.getparent().find("Name") or node.getparent().find("Ürün_Adı")
            adi = adi_node.text.strip() if adi_node is not None else ""
            records.append({"kod":kod,"adi":adi})
    # Genel tarama
    for elem in root.iter():
        txt = (elem.text or "").strip()
        if re.search(r"[A-Za-z0-9]", txt) and len(txt)<100:
            for kod in re.findall(r"\b[A-Za-z0-9\-\._]{5,20}\b", txt):
                adi = txt.replace(kod,"").strip(" -:;:")
                records.append({"kod":kod,"adi":adi})
    return pd.DataFrame(records).drop_duplicates(subset=["kod","adi"])

if u_order and u_invoice:
    df_siparis = extract_items(u_order)
    df_fatura  = extract_items(u_invoice)
    st.subheader("Sipariş Kayıtları");   st.dataframe(df_siparis)
    st.subheader("Fatura Kayıtları");    st.dataframe(df_fatura)

    # match list hazırlığı
    choices = df_siparis["kod"].tolist()

    results = []
    for _, f_row in df_fatura.iterrows():
        # kod bazlı arama
        m = process.extractOne(f_row["kod"], choices, scorer=fuzz.ratio)
        if m:
            best_kod, kod_score, idx = m
            # ürün adı bazlı dezavantajı ele
            if kod_score < threshold * w_code and f_row["adi"]:
                m2 = process.extractOne(f_row["adi"], df_siparis["adi"].tolist(), scorer=fuzz.partial_ratio)
                if m2:
                    best_name, name_score, idx2 = m2
                    total = w_code*kod_score + w_name*name_score
                    idx = idx2 if total > kod_score else idx
                    best_score = total
                else:
                    best_score = kod_score
            else:
                best_score = kod_score
        else:
            idx, best_score = None, 0

        matched = df_siparis.iloc[idx] if idx is not None else {"kod":"","adi":""}
        status = "EŞLEŞTİ" if best_score>=threshold else "EŞLEŞMEDİ"
        results.append({
            "fatura_kodu": f_row["kod"],
            "fatura_adi":  f_row["adi"],
            "siparis_kodu": matched["kod"],
            "siparis_adi":  matched["adi"],
            "eşleşme_oranı (%)": round(best_score,1),
            "durum": status
        })

    df_result = pd.DataFrame(results)
    st.subheader("Eşleştirme Sonuçları")
    st.dataframe(df_result)

    def to_excel(df):
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w: df.to_excel(w,index=False)
        return out.getvalue()

    data = to_excel(df_result)
    st.download_button("Excel İndir", data, file_name="sonuclar.xlsx")



