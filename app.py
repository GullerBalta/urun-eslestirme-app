
import streamlit as st
import pandas as pd
import re
from rapidfuzz import process, fuzz
from io import BytesIO
from lxml import etree
import json
import os
import sqlite3
from datetime import datetime

# Sayfa ayarı
st.set_page_config(layout="wide")
st.title("📦 Akıllı Sipariş | Fatura Karşılaştırma ve Tedarikçi Ekleme Sistemi")

# 🎯 Parametreler
threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
w_code = st.slider("📊 Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
w_name = 1 - w_code

# 📁 Dosya yükleyiciler
u_order = st.file_uploader("📤 Sipariş Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])
u_invoice = st.file_uploader("📤 Fatura Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])
supplier_name = st.text_input("🏷️ Tedarikçi Adı", "")

# 🧠 Veritabanı kurulum
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

# 🧠 Öğrenme fonksiyonu
def save_learned_match(supplier, invoice_code, order_code, invoice_name, order_name, score):
    conn = sqlite3.connect("learning.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO learned_matches (supplier_name, invoice_code, order_code, invoice_name, order_name, score, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (supplier, invoice_code, order_code, invoice_name, order_name, score, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# 🎯 Eşleşme seviyesi
def eslesme_seviyesi(puan):
    if puan >= 97:
        return "🟢 Mükemmel"
    elif puan >= 90:
        return "🟡 İyi"
    elif puan >= 80:
        return "🔵 Orta"
    else:
        return "⚪ Düşük"

# 🔐 Admin giriş
admin_user = "admin"
admin_password = "1234"

username = st.text_input("🔐 Admin Girişi (Sadece Senin İçin)", type="default")
password = st.text_input("🔑 Şifre", type="password")

is_admin = (username == admin_user and password == admin_password)

if is_admin:
    st.success("✅ Giriş başarılı. Yönetici paneli aktif.")

    # Veritabanı indir
    if os.path.exists("learning.db"):
        with open("learning.db", "rb") as f:
            st.download_button("📥 Öğrenme Veritabanını İndir (.db)", f, file_name="learning.db")

    # Öğrenilen kayıtları göster
    if st.button("📂 Öğrenilen Kayıtları Göster"):
        conn = sqlite3.connect("learning.db")
        df_learned = pd.read_sql_query("SELECT * FROM learned_matches", conn)
        conn.close()
        st.dataframe(df_learned)

elif username or password:
    st.warning("❌ Giriş başarısız. Lütfen bilgileri kontrol edin.")

# 📊 Eşleştirme işlemi
if u_order and u_invoice and supplier_name.strip():
    # Dosyaları oku
    df_order = pd.read_xml(u_order) if u_order.name.endswith(".xml") else pd.read_csv(u_order)
    df_invoice = pd.read_xml(u_invoice) if u_invoice.name.endswith(".xml") else pd.read_csv(u_invoice)

    # Kolon kontrolleri
    for col in ["urun_kodu", "urun_adi"]:
        if col not in df_order.columns:
            st.error(f"❌ Sipariş dosyasında '{col}' sütunu bulunamadı.")
            st.stop()
        if col not in df_invoice.columns:
            st.error(f"❌ Fatura dosyasında '{col}' sütunu bulunamadı.")
            st.stop()

    # Kodları ve adları al
    order_codes = df_order["urun_kodu"].astype(str)
    invoice_codes = df_invoice["urun_kodu"].astype(str)
    order_names = df_order["urun_adi"].astype(str)
    invoice_names = df_invoice["urun_adi"].astype(str)

    eslesen_kayitlar = []

    for i_code, i_name in zip(invoice_codes, invoice_names):
        best_match = None
        best_score = 0
        best_o_code, best_o_name = "", ""

        for o_code, o_name in zip(order_codes, order_names):
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

        # Öğrenme
        if best_score >= 97:
            save_learned_match(
                supplier=supplier_name.strip(),
                invoice_code=i_code,
                order_code=best_o_code,
                invoice_name=i_name,
                order_name=best_o_name,
                score=round(best_score, 2)
            )

    df_results = pd.DataFrame(eslesen_kayitlar)

    if not df_results.empty:
        st.subheader("🔍 Eşleşen Kayıtlar")
        st.dataframe(df_results, use_container_width=True)
    else:
        st.warning("⚠️ Eşleşme bulunamadı.")
