import streamlit as st
import pandas as pd
import re
from rapidfuzz import fuzz, process
from io import BytesIO
from lxml import etree
import json
import os

st.set_page_config(layout="wide")
st.title("📦 Akıllı Sipariş | Fatura Karşılaştırma ve Tedarikçi Ekleme Sistemi")

# Giriş durumu
if "giris_yapildi" not in st.session_state:
    st.session_state.giris_yapildi = False

# Kullanıcı Girişi
if not st.session_state.giris_yapildi:
    with st.expander("🔐 Giriş Yap (Tedarikçi Şablonları için)"):
        username = st.text_input("Kullanıcı Adı")
        password = st.text_input("Şifre", type="password")
        if st.button("Giriş"):
            if username == "guller" and password == "abc123":
                st.session_state.giris_yapildi = True
                st.success("✅ Giriş başarılı!")
            else:
                st.error("❌ Geçersiz kullanıcı adı veya şifre.")

# Benzerlik eşiği ve ağırlıklar
threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
w_code = st.slider("📊 Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
w_name = 1 - w_code

# Dosya yükleme
u_order = st.file_uploader("📤 Sipariş Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])
u_invoice = st.file_uploader("📤 Fatura Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])

# Tedarikçi adı
supplier_name = st.text_input("🔖 Tedarikçi Adı (şablon tanımlamak için)")
# Şablon dosyasını yükle
def load_supplier_patterns():
    if os.path.exists("supplier_patterns.json"):
        with open("supplier_patterns.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Kod normalizasyonu (genel)
def normalize_code(code):
    if pd.isna(code):
        return ""
    code = str(code).lower()
    code = re.sub(r'[^a-z0-9]', '', code)  # harf ve rakam dışı karakterleri kaldır
    return code

# Tedarikçiye özel pattern uygula
def apply_supplier_patterns(code, supplier):
    patterns = load_supplier_patterns()
    if supplier in patterns:
        pattern = patterns[supplier]
        if pattern.get("remove_prefix"):
            code = re.sub(pattern["remove_prefix"], "", code)
        if pattern.get("remove_suffix"):
            code = re.sub(pattern["remove_suffix"], "", code)
    return code

# Şablon tanımlama ve listeleme (sadece giriş yapmış kullanıcılar görebilir)
if st.session_state.giris_yapildi:
    prefix = st.text_input("Ön Ek Kaldır (Regex)", "^0+")
    suffix = st.text_input("Son Ek Kaldır (Regex)", "")

    if st.button("💡 Bu tedarikçiye özel şablonu kaydet"):
        patterns = load_supplier_patterns()
        patterns[supplier_name] = {"remove_prefix": prefix, "remove_suffix": suffix}
        with open("supplier_patterns.json", "w", encoding="utf-8") as f:
            json.dump(patterns, f, indent=2, ensure_ascii=False)
        st.success(f"✅ '{supplier_name}' için şablon kaydedildi.")

    if st.checkbox("📂 Kayıtlı Tedarikçi Şablonlarını Göster / Gizle"):
        patterns = load_supplier_patterns()
        if patterns:
            st.subheader("📋 Kayıtlı Şablonlar")
            st.json(patterns)
            json_str = json.dumps(patterns, indent=2, ensure_ascii=False)
            json_bytes = BytesIO(json_str.encode("utf-8"))
            st.download_button("📥 Şablonları JSON Olarak İndir", data=json_bytes, file_name="supplier_patterns.json", mime="application/json")
        else:
            st.info("🔍 Henüz kayıtlı bir şablon yok.")
# Kolon isimlerini temizle (ön işlem)
def clean_column_name(name):
    name = name.strip()
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^\w\-\.]', '', name)
    return name

# Ürün adı normalize
def normalize_name(name):
    name = str(name).lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

# Excel, CSV dosyalarını XML'e çevir
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

# XML içinden ürün kodu ve adı çıkar
def extract_items(xml_file, supplier_name=None):
    tree = etree.parse(xml_file)
    root = tree.getroot()
    records = []
    for elem in root.iter():
        txt = (elem.text or "").strip()
        if re.search(r"[A-Za-z0-9]", txt) and len(txt) < 100:
            for kod in re.findall(r"\b[A-Za-z0-9\-\._]{3,25}\b", txt):
                adi = txt.replace(kod, "").strip(" -:;:")
                kod_cleaned = apply_supplier_patterns(kod, supplier_name)
                records.append({
                    "kod": kod_cleaned,
                    "adi": adi
                })
    return pd.DataFrame(records).drop_duplicates(subset=["kod", "adi"])
# Kolon isimlerini temizle (ön işlem)
def clean_column_name(name):
    name = name.strip()
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^\w\-\.]', '', name)
    return name

# Ürün adı normalize
def normalize_name(name):
    name = str(name).lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

# Excel, CSV dosyalarını XML'e çevir
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

# XML içinden ürün kodu ve adı çıkar
def extract_items(xml_file, supplier_name=None):
    tree = etree.parse(xml_file)
    root = tree.getroot()
    records = []
    for elem in root.iter():
        txt = (elem.text or "").strip()
        if re.search(r"[A-Za-z0-9]", txt) and len(txt) < 100:
            for kod in re.findall(r"\b[A-Za-z0-9\-\._]{3,25}\b", txt):
                adi = txt.replace(kod, "").strip(" -:;:")
                kod_cleaned = apply_supplier_patterns(kod, supplier_name)
                records.append({
                    "kod": kod_cleaned,
                    "adi": adi
                })
    return pd.DataFrame(records).drop_duplicates(subset=["kod", "adi"])
