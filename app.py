import streamlit as st
import pandas as pd
import re
from rapidfuzz import process, fuzz
from io import BytesIO
from lxml import etree
import json
import os
import sqlite3
import bcrypt
from datetime import datetime

# -------------------- DATABASE INIT -------------------- #
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    ''')
    conn.commit()
    conn.close()

def add_user(username, password, role='user'):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)", (username, hashed, role))
    conn.commit()
    conn.close()

def authenticate(username, password):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    if result and bcrypt.checkpw(password.encode('utf-8'), result[0]):
        return True
    return False

def get_user_role(username):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else "user"

def log_user_action(username, action_desc):
    with open("logs.txt", "a", encoding="utf-8") as f:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{now}] {username}: {action_desc}\n")

# -------------------- DATA PROCESSING -------------------- #
def eslesme_seviyesi(puan):
    if puan >= 97: return "🟢 Mükemmel"
    elif puan >= 90: return "🟡 Çok İyi"
    elif puan >= 80: return "🟠 İyi"
    elif puan >= 65: return "🔴 Zayıf"
    else: return "⚫ Farklı Ürün"

def eslesmeme_seviyesi(puan):
    if puan <= 20: return "⚪ Şüpheli eşleşmeme, dikkatli kontrol"
    elif puan <= 34: return "🔵 Şüpheli, kontrol edilmeli"
    else: return "⚫ Muhtemelen farklı ürün"

def normalize_code(code):
    return re.sub(r'[^A-Za-z0-9]', '', str(code))

def normalize_name(name):
    name = str(name).lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def load_supplier_patterns():
    if os.path.exists("supplier_patterns.json"):
        with open("supplier_patterns.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_supplier_pattern(name, pattern):
    patterns = load_supplier_patterns()
    patterns[name] = pattern
    with open("supplier_patterns.json", "w", encoding="utf-8") as f:
        json.dump(patterns, f, indent=2, ensure_ascii=False)

def clean_with_supplier_pattern(code, pattern):
    code = str(code)
    if "remove_prefix" in pattern:
        code = re.sub(pattern["remove_prefix"], "", code)
    if "remove_suffix" in pattern:
        code = re.sub(pattern["remove_suffix"], "", code)
    return code

def save_learned_match(supplier, match):
    filename = "matched_pairs.json"
    data = {}
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
    if supplier not in data:
        data[supplier] = []
    data[supplier].append(match)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def extract_items(xml_file, supplier_name=None):
    tree = etree.parse(xml_file)
    root = tree.getroot()
    records = []
    patterns = load_supplier_patterns()
    supplier_pattern = patterns.get(supplier_name, {}) if supplier_name else {}
    for elem in root.iter():
        txt = (elem.text or "").strip()
        if re.search(r"[A-Za-z0-9]", txt) and len(txt) < 100:
            for kod in re.findall(r"\b[A-Za-z0-9\-\._]{5,20}\b", txt):
                adi = txt.replace(kod, "").strip(" -:;")
                kod = clean_with_supplier_pattern(kod, supplier_pattern)
                records.append({"kod": kod, "adi": adi})
    return pd.DataFrame(records).drop_duplicates(subset=["kod", "adi"])

# -------------------- UI -------------------- #
st.set_page_config(layout="wide")
st.title("📦 Akıllı Sipariş | Girişli ve Yönetici Erişimli Sistem")

init_db()
add_user("admin", "1234", role="admin")  # Admin hesabı örnek (ilk çalıştırmada oluştur)

if "username" not in st.session_state:
    st.subheader("🔐 Giriş Yapın")
    username = st.text_input("Kullanıcı Adı")
    password = st.text_input("Şifre", type="password")
    if st.button("Giriş"):
        if authenticate(username, password):
            st.session_state.username = username
            st.success(f"👋 Hoş geldin, {username}!")
            st.experimental_rerun()
        else:
            st.error("❌ Geçersiz kullanıcı adı veya şifre.")
else:
    st.sidebar.write(f"👤 Giriş Yapan: `{st.session_state.username}`")
    role = get_user_role(st.session_state.username)

    threshold = st.sidebar.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
    w_code = st.sidebar.slider("📊 Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
    w_name = 1 - w_code

    supplier_name = st.text_input("🔖 Tedarikçi Adı")
    prefix = st.text_input("Ön Ek Kaldır (Regex)", "^XYZ")
    suffix = st.text_input("Son Ek Kaldır (Regex)", "-TR$")

    if st.button("💡 Bu tedarikçiye özel şablonu kaydet"):
        save_supplier_pattern(supplier_name, {"remove_prefix": prefix, "remove_suffix": suffix})
        st.success(f"✅ '{supplier_name}' için şablon kaydedildi.")

    u_order = st.file_uploader("📤 Sipariş Dosyası", type=["xml", "csv", "xls", "xlsx", "txt"])
    u_invoice = st.file_uploader("📤 Fatura Dosyası", type=["xml", "csv", "xls", "xlsx", "txt"])

    if u_order and u_invoice:
        df_order = extract_items(u_order).head(5000)
        df_invoice = extract_items(u_invoice, supplier_name).head(5000)
        st.success("✅ Veriler başarıyla yüklendi.")
        results = []
        normalized_order_kodlar = [normalize_code(k) for k in df_order["kod"]]
        normalized_order_adlar = [normalize_name(a) for a in df_order["adi"]]

        for _, f_row in df_invoice.iterrows():
            f_kod_norm = normalize_code(f_row["kod"])
            kod_eslesme = process.extractOne(f_kod_norm, normalized_order_kodlar, scorer=fuzz.ratio)
            kod_score, name_score, idx = 0, 0, None
            if kod_eslesme:
                _, kod_score, idx = kod_eslesme

            if f_row["adi"]:
                f_name_norm = normalize_name(f_row["adi"])
                name_eslesme = process.extractOne(f_name_norm, normalized_order_adlar, scorer=fuzz.partial_ratio)
                if name_eslesme:
                    _, name_score, idx2 = name_eslesme
                    combined_score = w_code * kod_score + w_name * name_score
                    if combined_score > kod_score:
                        idx = idx2
                        kod_score = combined_score

            matched = df_order.iloc[idx] if idx is not None else {"kod": "", "adi": ""}
            durum = "EŞLEŞTİ" if kod_score >= threshold else "EŞLEŞMEDİ"

            if durum == "EŞLEŞTİ":
                save_learned_match(supplier_name, {
                    "fatura_kodu": f_row["kod"],
                    "siparis_kodu": matched["kod"],
                    "fatura_adi": f_row["adi"],
                    "siparis_adi": matched["adi"]
                })

            results.append({
                "Fatura Kodu": f_row["kod"],
                "Fatura Adı": f_row["adi"],
                "Sipariş Kodu": matched["kod"],
                "Sipariş Adı": matched["adi"],
                "Eşleşme Oranı (%)": round(kod_score, 1),
                "Durum": durum
            })

        df_result = pd.DataFrame(results).sort_values(by="Eşleşme Oranı (%)", ascending=False)
        df_eslesen = df_result[df_result["Durum"] == "EŞLEŞTİ"].copy().reset_index(drop=True)
        df_eslesen["Seviye"] = df_eslesen["Eşleşme Oranı (%)"].apply(eslesme_seviyesi)

        df_eslesmeyen = df_result[df_result["Durum"] == "EŞLEŞMEDİ"].copy().reset_index(drop=True)
        df_eslesmeyen["Eşleşmeme Oranı (%)"] = 100 - df_eslesmeyen["Eşleşme Oranı (%)"]
        df_eslesmeyen["Seviye"] = df_eslesmeyen["Eşleşmeme Oranı (%)"].apply(eslesmeme_seviyesi)
        df_eslesmeyen = df_eslesmeyen.drop(columns=["Eşleşme Oranı (%)"])

        st.subheader("✅ Eşleşen Kayıtlar")
        st.dataframe(df_eslesen)

        st.subheader("❌ Eşleşmeyen Kayıtlar")
        st.dataframe(df_eslesmeyen)

        log_user_action(st.session_state.username, f"{len(df_eslesen)} eşleşme, {len(df_eslesmeyen)} eşleşmeme")

        def to_excel(df1, df2):
            out = BytesIO()
            with pd.ExcelWriter(out, engine="openpyxl") as writer:
                df1.to_excel(writer, sheet_name="Eslesen", index=False)
                df2.to_excel(writer, sheet_name="Eslesmeyen", index=False)
            return out.getvalue()

        excel_data = to_excel(df_eslesen, df_eslesmeyen)
        st.download_button("📥 Excel İndir", data=excel_data, file_name="eslestirme_sonuclari.xlsx")

    if role == "admin":
        st.sidebar.markdown("## 🔐 Yönetici Paneli")
        tab = st.sidebar.radio("Veri", ["👁️ Öğrenilenler", "📁 Loglar"])
        if tab == "👁️ Öğrenilenler":
            st.subheader("📘 Tedarikçi Öğrenilen Verileri")
            if os.path.exists("matched_pairs.json"):
                with open("matched_pairs.json", "r", encoding="utf-8") as f:
                    st.json(json.load(f))
        elif tab == "📁 Loglar":
            st.subheader("📄 Kullanıcı Log Kayıtları")
            if os.path.exists("logs.txt"):
                with open("logs.txt", "r", encoding="utf-8") as f:
                    logs = f.read()
                    st.text(logs)

