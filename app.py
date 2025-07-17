import streamlit as st
import pandas as pd
import re
from rapidfuzz import fuzz
from io import BytesIO
from lxml import etree
import os
import sqlite3
from datetime import datetime

st.set_page_config(layout="wide")
st.title("📦 Akıllı Sipariş | Fatura Karşılaştırma ve Tedarikçi Ekleme Sistemi")

threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
w_code = st.slider("📊 Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
w_name = 1 - w_code

u_order = st.file_uploader("📤 Sipariş Dosyasını Yükleyin", type=["xml"])
u_invoice = st.file_uploader("📤 Fatura Dosyasını Yükleyin", type=["xml"])
supplier_name = st.text_input("🏷️ Tedarikçi Adı", "")

admin_user = "admin"
admin_password = "1234"
username = st.text_input("🔐 Admin Girişi", type="default")
password = st.text_input("🔑 Şifre", type="password")

is_admin = (username == admin_user and password == admin_password)

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

def extract_urun_kodlari_from_xml(file, tag_name="Ürün_Numarası"):
    tree = etree.parse(file)
    root = tree.getroot()
    return [elem.text.strip() for elem in root.iter(tag_name) if elem.text]

if is_admin:
    st.success("✅ Giriş başarılı. Yönetici paneli aktif.")
    if os.path.exists("learning.db"):
        with open("learning.db", "rb") as f:
            st.download_button("📥 Öğrenme Veritabanını İndir (.db)", f, file_name="learning.db")
    if st.button("📂 Öğrenilen Kayıtları Göster"):
        conn = sqlite3.connect("learning.db")
        df_learned = pd.read_sql_query("SELECT * FROM learned_matches", conn)
        conn.close()
        st.dataframe(df_learned)
elif username or password:
    st.warning("❌ Giriş başarısız. Lütfen bilgileri kontrol edin.")

# Ana eşleştirme işlemi
if u_order and u_invoice and supplier_name.strip():
    order_codes = extract_urun_kodlari_from_xml(u_order)
    invoice_codes = extract_urun_kodlari_from_xml(u_invoice)

    order_names = [""] * len(order_codes)
    invoice_names = [""] * len(invoice_codes)

    eslesen_kayitlar = []

    for i_code, i_name in zip(invoice_codes, invoice_names):
        best_score = 0
        best_o_code = ""
        for o_code, o_name in zip(order_codes, order_names):
            score_code = fuzz.token_sort_ratio(i_code, o_code)
            score_name = fuzz.token_sort_ratio(i_name, o_name)
            total_score = (score_code * w_code + score_name * w_name)
            if total_score > best_score:
                best_score = total_score
                best_o_code = o_code

        eslesen_kayitlar.append({
            "Fatura Kodu": i_code,
            "Sipariş Kodu": best_o_code,
            "Eşleşme Oranı (%)": round(best_score, 2),
            "Eşleşme Seviyesi": eslesme_seviyesi(best_score)
        })

        if best_score >= 97:
            save_learned_match(supplier_name.strip(), i_code, best_o_code, "", "", best_score)

    df_results = pd.DataFrame(eslesen_kayitlar)
    st.subheader("🔍 Eşleşen Kayıtlar")
    st.dataframe(df_results, use_container_width=True)


