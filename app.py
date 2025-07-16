import streamlit as st
import pandas as pd
import re
from rapidfuzz import process, fuzz
from io import BytesIO
from lxml import etree

st.set_page_config(layout="wide")
st.title("📦 Akıllı Sipariş | Fatura Karşılaştırma ve Tedarikçi Ekleme Sistemi")

threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
w_code = st.slider("📊 Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
w_name = 1 - w_code

u_order = st.file_uploader("📤 Sipariş Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])
u_invoice = st.file_uploader("📤 Fatura Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])

def normalize_code(text):
    if pd.isna(text):
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", str(text)).upper()

def read_file(uploaded_file):
    if uploaded_file.name.endswith(".xml"):
        tree = etree.parse(uploaded_file)
        root = tree.getroot()
        data = []
        for elem in root.iter():
            if elem.text and elem.text.strip().isdigit():
                data.append({"kod": elem.text.strip()})
        return pd.DataFrame(data)
    elif uploaded_file.name.endswith(".csv"):
        return pd.read_csv(uploaded_file, dtype={"kod": str})
    elif uploaded_file.name.endswith((".xls", ".xlsx")):
        return pd.read_excel(uploaded_file, dtype={"kod": str})
    elif uploaded_file.name.endswith(".txt"):
        return pd.read_csv(uploaded_file, sep="\t", dtype={"kod": str})
    return pd.DataFrame()

def match_data(order_df, invoice_df):
    results = []
    for _, o_row in order_df.iterrows():
        o_code = normalize_code(o_row["kod"])
        best_match = process.extractOne(
            o_code,
            invoice_df["kod"].apply(normalize_code),
            scorer=fuzz.ratio
        )
        if best_match and best_match[1] >= threshold:
            results.append({
                "Sipariş Kodu": o_code,
                "Fatura Kodu": best_match[0],
                "Benzerlik (%)": best_match[1]
            })
    return pd.DataFrame(results)

if u_order and u_invoice:
    order_df = read_file(u_order)
    invoice_df = read_file(u_invoice)

    if "kod" not in order_df.columns or "kod" not in invoice_df.columns:
        st.error("Her iki dosyada da 'kod' adlı bir sütun bulunmalı.")
    else:
        st.subheader("📋 Sipariş Verileri")
        st.dataframe(order_df)
        st.subheader("📋 Fatura Verileri")
        st.dataframe(invoice_df)

        matched_df = match_data(order_df, invoice_df)
        st.subheader("✅ Eşleşen Kayıtlar")
        st.dataframe(matched_df)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            matched_df.to_excel(writer, index=False, sheet_name="Eslestirmeler")
        st.download_button(
            label="📥 Eşleşme Sonuçlarını İndir",
            data=output.getvalue(),
            file_name="eslesme_sonuclari.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


