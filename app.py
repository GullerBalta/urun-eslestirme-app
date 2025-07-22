import streamlit as st
import pandas as pd
import re
from rapidfuzz import process, fuzz
from io import BytesIO
from lxml import etree
import json
import os
from streamlit import experimental_rerun  # Çıkış sonrası sayfa yenileme

# Sayfa ayarları
st.set_page_config(layout="wide")
st.title("📦 Akıllı Sipariş | Fatura Karşılaştırma ve Tedarikçi Ekleme Sistemi")

# Oturum ve form durumu
if "giris_yapildi" not in st.session_state:
    st.session_state.giris_yapildi = False
if "login_user" not in st.session_state:
    st.session_state.login_user = ""
if "login_pass" not in st.session_state:
    st.session_state.login_pass = ""
if "login_expanded" not in st.session_state:
    st.session_state.login_expanded = True

# 🔐 Giriş Paneli (Giriş ve Çıkış butonları yan yana)
with st.expander("🔐 Giriş Yap (Sadece şablon işlemleri için)", expanded=st.session_state.login_expanded):
    st.session_state.login_user = st.text_input("Kullanıcı Adı", value=st.session_state.login_user, key="login_user_input")
    st.session_state.login_pass = st.text_input("Şifre", value=st.session_state.login_pass, type="password", key="login_pass_input")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Giriş", key="login_button"):
            if st.session_state.login_user == "guller" and st.session_state.login_pass == "abc123":
                st.session_state.giris_yapildi = True
                st.session_state.login_expanded = True
                st.success("✅ Giriş başarılı!")
            else:
                st.error("❌ Geçersiz kullanıcı adı veya şifre.")

    with col2:
        if st.session_state.giris_yapildi:
            if st.button("Çıkış Yap", key="logout_button"):
                st.session_state.giris_yapildi = False
                st.session_state.login_user = ""
                st.session_state.login_pass = ""
                st.session_state.login_expanded = False
                st.success("🚪 Başarıyla çıkış yaptınız.")
                experimental_rerun()

# 🔧 Parametreler
threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
w_code = st.slider("📊 Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
w_name = 1 - w_code

# 📤 Dosya yükleme
u_order = st.file_uploader("📤 Sipariş Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"], key="order_upload")
u_invoice = st.file_uploader("📤 Fatura Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"], key="invoice_upload")

# Yardımcı Fonksiyonlar
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
# 🔖 Tedarikçi Bilgisi ve Regex Girdileri (herkese açık)
supplier_name = st.text_input("🔖 Tedarikçi Adı (şablon tanımlamak için veya yüklenen dosyaya özel işleme)", key="supplier_name")
prefix = st.text_input("🔎 Ön Ek Kaldır (Regex)", "^XYZ", key="regex_prefix")
suffix = st.text_input("🔍 Son Ek Kaldır (Regex)", "-TR$", key="regex_suffix")

# XML dönüştürme fonksiyonu
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

# Şablon işlemleri
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

# 👤 Giriş yapmış kullanıcılar için şablon işlemleri
if st.session_state.giris_yapildi:
    if st.button("💾 Bu tedarikçiye özel şablonu kaydet"):
        save_supplier_pattern(supplier_name, {"remove_prefix": prefix, "remove_suffix": suffix})
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
            st.info("🔍 Henüz kayıtlı şablon yok.")

# XML'den veri çıkarma
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
                kod = re.sub(prefix, "", kod)
                kod = re.sub(suffix, "", kod)
                if supplier_pattern:
                    kod = re.sub(supplier_pattern.get("remove_prefix", ""), "", kod)
                    kod = re.sub(supplier_pattern.get("remove_suffix", ""), "", kod)
                records.append({"kod": kod, "adi": adi})
    return pd.DataFrame(records).drop_duplicates(subset=["kod", "adi"])

# Eşleşme seviyeleri
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

# Eşleştirme işlemi
if u_order and u_invoice:
    converted_order = convert_to_xml(u_order)
    converted_invoice = convert_to_xml(u_invoice)

    if converted_order and converted_invoice:
        df_siparis = extract_items(converted_order, supplier_name).head(5000)
        df_fatura = extract_items(converted_invoice, supplier_name).head(5000)

        st.subheader("📦 Sipariş Verileri")
        st.dataframe(df_siparis)

        st.subheader("🧾 Fatura Verileri")
        st.dataframe(df_fatura)

        with st.spinner("🔄 Eşleştirme yapılıyor..."):
            results = []
            normalized_siparis_kodlar = [normalize_code(k) for k in df_siparis["kod"]]
            normalized_siparis_adlar = [normalize_name(ad) for ad in df_siparis["adi"]]

            for _, f_row in df_fatura.iterrows():
                f_kod_norm = normalize_code(f_row["kod"])
                kod_eslesme = process.extractOne(f_kod_norm, normalized_siparis_kodlar, scorer=fuzz.ratio)
                kod_score, name_score, idx = 0, 0, None
                if kod_eslesme:
                    _, kod_score, idx = kod_eslesme
                if f_row["adi"]:
                    f_name_norm = normalize_name(f_row["adi"])
                    name_eslesme = process.extractOne(f_name_norm, normalized_siparis_adlar, scorer=fuzz.partial_ratio)
                    if name_eslesme:
                        _, name_score, idx2 = name_eslesme
                        combined = w_code * kod_score + w_name * name_score
                        if combined > kod_score:
                            kod_score = combined
                            idx = idx2
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
            df_eslesen = df_result[df_result["Durum"] == "EŞLEŞTİ"].copy()
            df_eslesen["Seviye"] = df_eslesen["Eşleşme Oranı (%)"].apply(eslesme_seviyesi)

            df_eslesmeyen = df_result[df_result["Durum"] == "EŞLEŞMEDİ"].copy()
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

        dosya_adi = f"eslestirme_{supplier_name.strip().replace(' ', '_') or 'cikti'}.xlsx"
        st.download_button("📥 Excel İndir", data=to_excel(df_eslesen, df_eslesmeyen), file_name=dosya_adi)
