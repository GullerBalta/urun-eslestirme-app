import streamlit as st
import pandas as pd
from rapidfuzz import fuzz
import os
import sqlite3
from datetime import datetime

# Sayfa ayarı
st.set_page_config(layout="wide")
st.title("📦 Akıllı Sipariş | Ürün Kodu ile Fatura-Sipariş Eşleştirme Sistemi")

# 🎯 Parametreler
threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)

# 📁 Dosya yükleyiciler
u_order = st.file_uploader("📤 Sipariş Dosyasını Yükleyin (.xml)", type=["xml"])
u_invoice = st.file_uploader("📤 Fatura Dosyasını Yükleyin (.xml)", type=["xml"])
supplier_name = st.text_input("🏷️ Tedarikçi Adı", "")

# 🧠 Veritabanı kurulumu
def init_learning_db():
    conn = sqlite3.connect("learning.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learned_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_name TEXT,
            invoice_code TEXT,
            order_code TEXT,
            score REAL,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_learning_db()

# 🧠 Öğrenme fonksiyonu
def save_learned_match(supplier, invoice_code, order_code, score):
    conn = sqlite3.connect("learning.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO learned_matches (supplier_name, invoice_code, order_code, score, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (supplier, invoice_code, order_code, score, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# 🔐 Admin Giriş
admin_user = "admin"
admin_pass = "1234"

username = st.text_input("👤 Admin Kullanıcı Adı")
password = st.text_input("🔑 Şifre", type="password")

is_admin = (username == admin_user and password == admin_pass)

if is_admin:
    st.success("🔓 Yönetici girişi başarılı.")

    if os.path.exists("learning.db"):
        with open("learning.db", "rb") as f:
            st.download_button("📥 Veritabanını İndir", f, file_name="learning.db")

    if st.button("📂 Öğrenilen Kayıtları Göster"):
        conn = sqlite3.connect("learning.db")
        df_learned = pd.read_sql_query("SELECT * FROM learned_matches", conn)
        conn.close()
        st.dataframe(df_learned)

elif username or password:
    st.warning("❌ Giriş başarısız.")

# 📊 Eşleşme
if u_order and u_invoice and supplier_name.strip():
    df_order = pd.read_xml(u_order)
    df_invoice = pd.read_xml(u_invoice)

    # Kolon kontrolü
    if "urun_kodu" not in df_order.columns or "urun_kodu" not in df_invoice.columns:
        st.error("❌ Her iki dosyada da 'urun_kodu' sütunu olmalı.")
        st.stop()

    order_codes = df_order["urun_kodu"].astype(str)
    invoice_codes = df_invoice["urun_kodu"].astype(str)

    results = []

    for i_code in invoice_codes:
        best_score = 0
        best_o_code = ""

        for o_code in order_codes:
            score = fuzz.token_sort_ratio(i_code, o_code)
            if score > best_score:
                best_score = score
                best_o_code = o_code

        results.append({
            "Fatura Kodu": i_code,
            "Sipariş Kodu": best_o_code,
            "Eşleşme Oranı (%)": round(best_score, 2)
        })

        # Öğrenme kaydı
        if best_score >= threshold:
            save_learned_match(
                supplier=supplier_name.strip(),
                invoice_code=i_code,
                order_code=best_o_code,
                score=round(best_score, 2)
            )

    df_results = pd.DataFrame(results)

    if not df_results.empty:
        st.subheader("🔍 Eşleşen Kayıtlar")
        st.dataframe(df_results, use_container_width=True)
    else:
        st.warning("⚠️ Eşleşme bulunamadı.")
