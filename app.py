import streamlit as st
import bcrypt
import sqlite3
import pandas as pd
import re
from rapidfuzz import process, fuzz
from io import BytesIO
from lxml import etree
from datetime import datetime

st.set_page_config(layout="wide")
st.title("📦 Akıllı Sipariş | Giriş Kontrollü Karşılaştırma Sistemi")

# -------------------- VERİTABANI --------------------
DB_PATH = "users.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_user(username, password):
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if row and bcrypt.checkpw(password.encode(), row[0]):
        return True
    return False

# -------------------- OTURUM KONTROLÜ --------------------
init_db()
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.subheader("🔐 Giriş Yap veya Kayıt Ol")

    menu = st.radio("Seçenek", ["Giriş", "Kayıt Ol"])
    username = st.text_input("Kullanıcı Adı")
    password = st.text_input("Şifre", type="password")

    if menu == "Giriş":
        if st.button("Giriş Yap"):
            if verify_user(username, password):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.success(f"Hoş geldin, {username}!")
                st.experimental_rerun()
            else:
                st.error("❌ Kullanıcı adı veya şifre hatalı.")

    elif menu == "Kayıt Ol":
        if st.button("Kayıt Ol"):
            if add_user(username, password):
                st.success("✅ Kayıt başarılı, şimdi giriş yapabilirsiniz.")
            else:
                st.error("❌ Bu kullanıcı adı zaten mevcut.")
    st.stop()

# -------------------- GİRİŞ BAŞARILI: ANA UYGULAMA --------------------
if st.sidebar.button("🚪 Çıkış Yap"):
    st.session_state["authenticated"] = False
    st.experimental_rerun()

threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
w_code = st.slider("📊 Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
w_name = 1 - w_code

u_order = st.file_uploader("📤 Sipariş Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])
u_invoice = st.file_uploader("📤 Fatura Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])

def eslesme_seviyesi(puan):
    if puan >= 97: return "🟢 Mükemmel"
    elif puan >= 90: return "🟡 Çok İyi"
    elif puan >= 80: return "🟠 İyi"
    elif puan >= 65: return "🔴 Zayıf"
    else: return "⚫ Farklı Ürün"

def eslesmeme_seviyesi(puan):
    if puan <= 20: return "⚪ Şüpheli eşleşmeme"
    elif puan <= 34: return "🔵 Kontrol edilmeli"
    else: return "⚫ Muhtemelen farklı ürün"

def clean_column_name(name):
    name = name.strip()
    name = re.sub(r'\s+', '_', name)
    return re.sub(r'[^\w\-\.]', '', name)

def normalize_code(code): return re.sub(r'[^A-Za-z0-9]', '', str(code))
def normalize_name(name):
    name = str(name).lower()
    name = re.sub(r'[^\w\s]', '', name)
    return re.sub(r'\s+', ' ', name).strip()

def convert_to_xml(uploaded_file):
    file_type = uploaded_file.name.split('.')[-1].lower()
    try:
        if file_type == "xml":
            return uploaded_file
        elif file_type in ["csv", "txt"]:
            df = pd.read_csv(uploaded_file)
        elif file_type in ["xls", "xlsx"]:
            df = pd.read_excel(uploaded_file)
        else:
            st.error("❌ Desteklenmeyen dosya türü.")
            return None
        df.columns = [clean_column_name(col) for col in df.columns]
        root = etree.Element("Data")
        for _, row in df.iterrows():
            item_elem = etree.SubElement(root, "Item")
            for col, val in row.items():
                col_elem = etree.SubElement(item_elem, col)
                col_elem.text = str(val)
        xml_bytes = BytesIO()
        etree.ElementTree(root).write(xml_bytes, encoding='utf-8', xml_declaration=True)
        xml_bytes.seek(0)
        return xml_bytes
    except Exception as e:
        st.error(f"❌ XML'e dönüştürme hatası: {str(e)}")
        return None

def extract_items(xml_file):
    tree = etree.parse(xml_file)
    root = tree.getroot()
    records = []
    for elem in root.iter():
        txt = (elem.text or "").strip()
        if re.search(r"[A-Za-z0-9]", txt) and len(txt) < 100:
            for kod in re.findall(r"\b[A-Za-z0-9\-\._]{5,20}\b", txt):
                adi = txt.replace(kod, "").strip(" -:;:")
                records.append({"kod": kod, "adi": adi})
    return pd.DataFrame(records).drop_duplicates(subset=["kod", "adi"])

if u_order and u_invoice:
    converted_order = convert_to_xml(u_order)
    converted_invoice = convert_to_xml(u_invoice)

    if converted_order and converted_invoice:
        df_siparis = extract_items(converted_order).head(5000)
        df_fatura = extract_items(converted_invoice).head(5000)

        st.subheader("📦 Sipariş Verileri")
        st.dataframe(df_siparis)

        st.subheader("🧾 Fatura Verileri")
        st.dataframe(df_fatura)

        with st.spinner("🔄 Eşleştirme yapılıyor..."):
            results = []
            s_kodlar = df_siparis["kod"].tolist()
            s_adlar = df_siparis["adi"].tolist()
            norm_s_kodlar = [normalize_code(k) for k in s_kodlar]
            norm_s_adlar = [normalize_name(ad) for ad in s_adlar]

            for _, f_row in df_fatura.iterrows():
                f_kod_norm = normalize_code(f_row["kod"])
                kod_eslesme = process.extractOne(f_kod_norm, norm_s_kodlar, scorer=fuzz.ratio)
                kod_score, name_score, idx = 0, 0, None
                if kod_eslesme: _, kod_score, idx = kod_eslesme

                if f_row["adi"]:
                    f_name_norm = normalize_name(f_row["adi"])
                    name_eslesme = process.extractOne(f_name_norm, norm_s_adlar, scorer=fuzz.partial_ratio)
                    if name_eslesme:
                        _, name_score, idx2 = name_eslesme
                        combined = w_code * kod_score + w_name * name_score
                        if combined > kod_score:
                            idx = idx2
                            kod_score = combined

                matched = df_siparis.iloc[idx] if idx is not None else {"kod": "", "adi": ""}
                durum = "EŞLEŞTİ" if kod_score >= threshold else "EŞLEŞMEDİ"

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

        st.success("✅ Eşleştirme tamamlandı!")
        st.subheader("✅ Eşleşen Kayıtlar")
        st.dataframe(df_eslesen)

        st.subheader("❌ Eşleşmeyen Kayıtlar")
        st.dataframe(df_eslesmeyen)

        def to_excel(df1, df2):
            out = BytesIO()
            with pd.ExcelWriter(out, engine="openpyxl") as writer:
                df1.to_excel(writer, sheet_name="Eslesen", index=False)
                df2.to_excel(writer, sheet_name="Eslesmeyen", index=False)
            return out.getvalue()

        excel_data = to_excel(df_eslesen, df_eslesmeyen)
        st.download_button("📥 Excel İndir", data=excel_data, file_name="eslestirme_sonuclari.xlsx")



