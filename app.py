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

# 📦 Veritabanı kurulumu
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

# 🔐 Admin
admin_user = "admin"
admin_password = "1234"

username = st.text_input("🔐 Admin Girişi (Sadece Senin İçin)", type="default")
password = st.text_input("🔑 Şifre", type="password")
is_admin = (username == admin_user and password == admin_password)

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

# 🧠 XML'den otomatik ürün kodu ve adı çıkarma
def kod_ve_adlari_bul(dosya, min_karakter=5, max_karakter=25):
    tree = etree.parse(dosya)
    root = tree.getroot()
    kodlar = []
    adlar = []

    for elem in root.iter():
        if elem.text:
            metin = elem.text.strip()
            if re.fullmatch(r'[A-Za-z0-9\-\.\_]{%d,%d}' % (min_karakter, max_karakter), metin):
                kodlar.append(metin)
            elif len(metin) > 10 and " " in metin:
                adlar.append(metin)

    min_len = min(len(kodlar), len(adlar))
    return pd.DataFrame({
        "urun_kodu": kodlar[:min_len],
        "urun_adi": adlar[:min_len]
    })

# 📊 Eşleştirme
if u_order and u_invoice and supplier_name.strip():
    df_order = kod_ve_adlari_bul(u_order)
    df_invoice = kod_ve_adlari_bul(u_invoice)

    eslesen_kayitlar = []

    for i_code, i_name in zip(df_invoice["urun_kodu"], df_invoice["urun_adi"]):
        best_score = 0
        best_o_code, best_o_name = "", ""

        for o_code, o_name in zip(df_order["urun_kodu"], df_order["urun_adi"]):
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
                supplier=supplier_name.strip(),
                invoice_code=i_code,
                order_code=best_o_code,
                invoice_name=i_name,
                order_name=best_o_name,
                score=round(best_score, 2)
            )

    df_results = pd.DataFrame(eslesen_kayitlar)
    st.subheader("🔍 Eşleşen Kayıtlar")
    st.dataframe(df_results, use_container_width=True)


