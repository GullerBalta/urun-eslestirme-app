import streamlit as st
import pandas as pd
import re
from rapidfuzz import process, fuzz
from io import BytesIO
from lxml import etree
import json
import os

st.set_page_config(layout="wide")
st.title("📦 Akıllı Sipariş | Fatura Karşılaştırma ve Tedarikçi Ekleme Sistemi")

# Kullanıcı Girişi Durumu
if "giris_yapildi" not in st.session_state:
    st.session_state.giris_yapildi = False

if not st.session_state.giris_yapildi:
    with st.expander("🔐 Giriş Yap (Sadece Şablonları Görüntülemek İçin)"):
        username = st.text_input("Kullanıcı Adı")
        password = st.text_input("Şifre", type="password")
        if st.button("Giriş"):
            if username == "guller" and password == "abc123":
                st.session_state.giris_yapildi = True
                st.success("✅ Giriş başarılı!")
            else:
                st.error("❌ Hatalı kullanıcı adı veya şifre")

# Benzerlik ve Ağırlık Ayarları
threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
w_code = st.slider("📊 Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
w_name = 1 - w_code

# Dosya Yükleyiciler
u_order = st.file_uploader("📤 Sipariş Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])
u_invoice = st.file_uploader("📤 Fatura Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])
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

# 👇 ÖNEMLİ: Tedarikçiye özel kod temizleme
def apply_supplier_patterns(kod, supplier_name=None):
    patterns = load_supplier_patterns()
    if supplier_name and supplier_name in patterns:
        prefix = patterns[supplier_name].get("remove_prefix", "")
        suffix = patterns[supplier_name].get("remove_suffix", "")
        if prefix:
            kod = re.sub(prefix, "", kod)
        if suffix:
            kod = re.sub(suffix, "", kod)
    return kod
# 🏷️ Tedarikçi Adı (Şablon tanımı için)
supplier_name = st.text_input("🔖 Tedarikçi Adı (şablon tanımlamak için)")

if st.session_state.giris_yapildi:
    prefix = st.text_input("Ön Ek Kaldır (Regex)", "")
    suffix = st.text_input("Son Ek Kaldır (Regex)", "")

    if st.button("💡 Bu tedarikçiye özel şablonu kaydet"):
        save_supplier_pattern(supplier_name, {
            "remove_prefix": prefix,
            "remove_suffix": suffix
        })
        st.success(f"✅ '{supplier_name}' için şablon kaydedildi.")

    if st.checkbox("📂 Kayıtlı Tedarikçi Şablonlarını Göster / Gizle"):
        patterns = load_supplier_patterns()
        if patterns:
            st.subheader("📋 Kayıtlı Şablonlar")
            st.json(patterns)
            json_str = json.dumps(patterns, indent=2, ensure_ascii=False)
            st.download_button(
                "📥 Şablonları JSON Olarak İndir",
                data=BytesIO(json_str.encode("utf-8")),
                file_name="supplier_patterns.json",
                mime="application/json"
            )
        else:
            st.info("🔍 Henüz kayıtlı bir şablon yok.")

# 💾 CSV/XLSX/XML/TXT → XML dönüşüm
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
# 🏷️ Tedarikçi Adı (Şablon tanımı için)
supplier_name = st.text_input("🔖 Tedarikçi Adı (şablon tanımlamak için)")

if st.session_state.giris_yapildi:
    prefix = st.text_input("Ön Ek Kaldır (Regex)", "")
    suffix = st.text_input("Son Ek Kaldır (Regex)", "")

    if st.button("💡 Bu tedarikçiye özel şablonu kaydet"):
        save_supplier_pattern(supplier_name, {
            "remove_prefix": prefix,
            "remove_suffix": suffix
        })
        st.success(f"✅ '{supplier_name}' için şablon kaydedildi.")

    if st.checkbox("📂 Kayıtlı Tedarikçi Şablonlarını Göster / Gizle"):
        patterns = load_supplier_patterns()
        if patterns:
            st.subheader("📋 Kayıtlı Şablonlar")
            st.json(patterns)
            json_str = json.dumps(patterns, indent=2, ensure_ascii=False)
            st.download_button(
                "📥 Şablonları JSON Olarak İndir",
                data=BytesIO(json_str.encode("utf-8")),
                file_name="supplier_patterns.json",
                mime="application/json"
            )
        else:
            st.info("🔍 Henüz kayıtlı bir şablon yok.")

# 💾 CSV/XLSX/XML/TXT → XML dönüşüm
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
        dosya_adi = f"eslestirme_sonuclari_{supplier_name.strip().replace(' ', '_') or 'isimsiz'}.xlsx"

        st.download_button(
            "📥 Excel İndir",
            data=excel_data,
            file_name=dosya_adi,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

