import streamlit as st
import pandas as pd
from lxml import etree
import sqlite3
from rapidfuzz import fuzz
from datetime import datetime
import os

st.set_page_config(layout="wide")
st.title("📦 Akıllı Sipariş | Otomatik Ürün Kodu-Adı Tespiti ve Eşleştirme")

threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
w_code = st.slider("📊 Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
w_name = 1 - w_code

u_order = st.file_uploader("📤 Sipariş Dosyasını Yükleyin", type=["xml"])
u_invoice = st.file_uploader("📤 Fatura Dosyasını Yükleyin", type=["xml"])
supplier_name = st.text_input("🏷️ Tedarikçi Adı", "")

def init_learning_db():
    conn = sqlite3.connect("learning.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learned_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_name TEXT,
            invoice_code TEXT,
            order_code TEXT,
            invoice_name TEXT,
            order_name TEXT,
            score REAL,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_learning_db()

def save_learned_match(supplier, invoice_code, order_code, invoice_name, order_name, score):
    conn = sqlite3.connect("learning.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO learned_matches (supplier_name, invoice_code, order_code, invoice_name, order_name, score, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (supplier, invoice_code, order_code, invoice_name, order_name, score, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def eslesme_seviyesi(puan):
    if puan >= 97:
        return "🟢 Mükemmel"
    elif puan >= 90:
        return "🟡 İyi"
    elif puan >= 80:
        return "🔵 Orta"
    else:
        return "⚪ Düşük"

# 🔍 Otomatik XML alan bulucu
def parse_xml_auto_fields(uploaded_file):
    tree = etree.parse(uploaded_file)
    root = tree.getroot()

    urunler = []
    for elem in root.iter():
        kod = ""
        ad = ""
        if elem.text:
            text = elem.text.strip()
            if 5 <= len(text) <= 25 and any(c.isdigit() for c in text):
                kod = text
            if len(text) > 3 and any(c.isalpha() for c in text) and not kod:
                ad = text
        if kod or ad:
            urunler.append({"urun_kodu": kod, "urun_adi": ad})
    df = pd.DataFrame(urunler).drop_duplicates()
    df = df[(df["urun_kodu"] != "") & (df["urun_adi"] != "")]
    return df.reset_index(drop=True)

if u_order and u_invoice and supplier_name.strip():
    df_order = parse_xml_auto_fields(u_order)
    df_invoice = parse_xml_auto_fields(u_invoice)

    st.write("📦 Sipariş Verisi:", df_order.head())
    st.write("🧾 Fatura Verisi:", df_invoice.head())

    eslesen_kayitlar = []

    for _, f_row in df_invoice.iterrows():
        i_code, i_name = f_row["urun_kodu"], f_row["urun_adi"]
        best_score = 0
        best_o_code, best_o_name = "", ""

        for _, o_row in df_order.iterrows():
            o_code, o_name = o_row["urun_kodu"], o_row["urun_adi"]
            score_code = fuzz.token_sort_ratio(i_code, o_code)
            score_name = fuzz.token_sort_ratio(i_name, o_name)
            total_score = (score_code * w_code + score_name * w_name)

            if total_score > best_score:
                best_score = total_score
                best_o_code = o_code
                best_o_name = o_name

        eslesen_kayitlar.append({
            "Fatura Kodu": i_code,
            "Sipariş Kodu": best_o_code,
            "Fatura Adı": i_name,
            "Sipariş Adı": best_o_name,
            "Eşleşme Oranı (%)": round(best_score, 2),
            "Eşleşme Seviyesi": eslesme_seviyesi(best_score)
        })

        if best_score >= 97:
            save_learned_match(
                supplier=supplier_name,
                invoice_code=i_code,
                order_code=best_o_code,
                invoice_name=i_name,
                order_name=best_o_name,
                score=round(best_score, 2)
            )

    df_results = pd.DataFrame(eslesen_kayitlar)
    st.subheader("🔍 Eşleşen Kayıtlar")
    st.dataframe(df_results, use_container_width=True)



