import streamlit as st
import pandas as pd
import re
from rapidfuzz import process, fuzz
from io import BytesIO
from lxml import etree
import json
import os

# Sayfa ayarları
st.set_page_config(layout="wide")
st.title("📦 Akıllı Sipariş | Fatura Karşılaştırma ve Tedarikçi Ekleme Sistemi")

# Kullanıcı Girişi (sadece şablon işlemleri için)
if "giris_yapildi" not in st.session_state:
    st.session_state.giris_yapildi = False

with st.expander("🔐 Giriş Yap (Sadece şablon işlemleri için)"):
    username = st.text_input("Kullanıcı Adı")
    password = st.text_input("Şifre", type="password")
    if st.button("Giriş"):
        if username == "guller" and password == "abc123":
            st.session_state.giris_yapildi = True
            st.success("✅ Giriş başarılı!")
        else:
            st.error("❌ Geçersiz kullanıcı adı veya şifre.")

# Eşik ve ağırlık ayarları
threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
w_code = st.slider("📊 Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
w_name = 1 - w_code

# Dosya yükleme
u_order = st.file_uploader("📤 Sipariş Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])
u_invoice = st.file_uploader("📤 Fatura Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])

# Tedarikçi bilgisi
supplier_name = st.text_input("🔖 Tedarikçi Adı (şablon tanımlamak için)")

# Herkes için açık regex alanları
prefix = st.text_input("🔍 Ön Ek Kaldır (Regex)", "")
suffix = st.text_input("🔍 Son Ek Kaldır (Regex)", "")
def clean_column_name(name):
    name = name.strip()
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^\w\-\.]', '', name)
    return name

def normalize_code(code):
    return re.sub(r'^0+', '', re.sub(r'[^A-Za-z0-9]', '', str(code)))

def normalize_name(name):
    name = str(name).lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def convert_to_xml(uploaded_file):
    file_type = uploaded_file.name.split('.')[-1].lower()
    try:
        if file_type == "xml":
            return uploaded_file
        elif file_type in ["csv", "txt"]:
            df = pd.read_csv(uploaded_file, dtype=str)
        elif file_type in ["xls", "xlsx"]:
            df = pd.read_excel(uploaded_file, dtype=str)
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
        tree = etree.ElementTree(root)
        tree.write(xml_bytes, encoding='utf-8', xml_declaration=True)
        xml_bytes.seek(0)
        return xml_bytes
    except Exception as e:
        st.error(f"❌ XML'e dönüştürme hatası: {str(e)}")
        return None

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
                adi = txt.replace(kod, "").strip(" -:;:")
                # Tedarikçi şablonu varsa uygula, yoksa kullanıcıdan gelen regex'i kullan
                kod = re.sub(supplier_pattern.get("remove_prefix", prefix), "", kod)
                kod = re.sub(supplier_pattern.get("remove_suffix", suffix), "", kod)
                records.append({"kod": kod, "adi": adi})
    return pd.DataFrame(records).drop_duplicates(subset=["kod", "adi"])

def eslesme_seviyesi(puan):
    if puan >= 97:
        return "🟢 Mükemmel"
    elif puan >= 90:
        return "🟡 Çok İyi"
    elif puan >= 80:
        return "🟠 İyi"
    elif puan >= 65:
        return "🔴 Zayıf"
    else:
        return "⚫ Farklı Ürün"

def eslesmeme_seviyesi(puan):
    if puan <= 20:
        return "⚪ Şüpheli eşleşmeme"
    elif puan <= 34:
        return "🔵 Şüpheli, kontrol edilmeli"
    else:
        return "⚫ Muhtemelen farklı ürün"
def clean_column_name(name):
    name = name.strip()
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^\w\-\.]', '', name)
    return name

def normalize_code(code):
    return re.sub(r'^0+', '', re.sub(r'[^A-Za-z0-9]', '', str(code)))

def normalize_name(name):
    name = str(name).lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def convert_to_xml(uploaded_file):
    file_type = uploaded_file.name.split('.')[-1].lower()
    try:
        if file_type == "xml":
            return uploaded_file
        elif file_type in ["csv", "txt"]:
            df = pd.read_csv(uploaded_file, dtype=str)
        elif file_type in ["xls", "xlsx"]:
            df = pd.read_excel(uploaded_file, dtype=str)
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
        tree = etree.ElementTree(root)
        tree.write(xml_bytes, encoding='utf-8', xml_declaration=True)
        xml_bytes.seek(0)
        return xml_bytes
    except Exception as e:
        st.error(f"❌ XML'e dönüştürme hatası: {str(e)}")
        return None

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
                adi = txt.replace(kod, "").strip(" -:;:")
                # Tedarikçi şablonu varsa uygula, yoksa kullanıcıdan gelen regex'i kullan
                kod = re.sub(supplier_pattern.get("remove_prefix", prefix), "", kod)
                kod = re.sub(supplier_pattern.get("remove_suffix", suffix), "", kod)
                records.append({"kod": kod, "adi": adi})
    return pd.DataFrame(records).drop_duplicates(subset=["kod", "adi"])

def eslesme_seviyesi(puan):
    if puan >= 97:
        return "🟢 Mükemmel"
    elif puan >= 90:
        return "🟡 Çok İyi"
    elif puan >= 80:
        return "🟠 İyi"
    elif puan >= 65:
        return "🔴 Zayıf"
    else:
        return "⚫ Farklı Ürün"

def eslesmeme_seviyesi(puan):
    if puan <= 20:
        return "⚪ Şüpheli eşleşmeme"
    elif puan <= 34:
        return "🔵 Şüpheli, kontrol edilmeli"
    else:
        return "⚫ Muhtemelen farklı ürün"
