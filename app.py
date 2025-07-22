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

# Giriş kontrol
if "is_logged_in" not in st.session_state:
    st.session_state["is_logged_in"] = False

if not st.session_state["is_logged_in"]:
    with st.expander("🔐 Giriş Yap (Tedarikçi Şablonları için)"):
        username = st.text_input("Kullanıcı Adı")
        password = st.text_input("Şifre", type="password")
        if st.button("Giriş"):
            if username == "guller" and password == "abc123":
                st.session_state["is_logged_in"] = True
                st.success("✅ Giriş başarılı!")
            else:
                st.error("❌ Geçersiz kullanıcı adı veya şifre.")

# Ayarlar üstte
threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
w_code = st.slider("📊 Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
w_name = 1 - w_code
u_order = st.file_uploader("📤 Sipariş Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])
u_invoice = st.file_uploader("📤 Fatura Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])
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

def normalize_code(code):
    return re.sub(r'^0+', '', re.sub(r'[^A-Za-z0-9]', '', str(code)))

def normalize_name(name):
    name = str(name).lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def clean_column_name(name):
    name = name.strip()
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^\w\-\.]', '', name)
    return name

def convert_to_xml(uploaded_file):
    ext = uploaded_file.name.split('.')[-1].lower()
    try:
        if ext == "xml":
            return uploaded_file
        df = pd.read_csv(uploaded_file) if ext in ["csv", "txt"] else pd.read_excel(uploaded_file)
        df.columns = [clean_column_name(c) for c in df.columns]
        root = etree.Element("Data")
        for _, row in df.iterrows():
            item = etree.SubElement(root, "Item")
            for col, val in row.items():
                etree.SubElement(item, col).text = str(val)
        xml_bytes = BytesIO()
        etree.ElementTree(root).write(xml_bytes, encoding="utf-8", xml_declaration=True)
        xml_bytes.seek(0)
        return xml_bytes
    except:
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
    patterns = load_supplier_patterns()
    pattern = patterns.get(supplier_name, {}) if supplier_name else {}
    records = []
    for elem in root.iter():
        txt = (elem.text or "").strip()
        if re.search(r"[A-Za-z0-9]", txt) and len(txt) < 100:
            for kod in re.findall(r"\b[A-Za-z0-9\-\._]{5,20}\b", txt):
                adi = txt.replace(kod, "").strip(" -:;:")
                if pattern:
                    kod = re.sub(pattern.get("remove_prefix", "^$"), "", kod)
                    kod = re.sub(pattern.get("remove_suffix", "$^"), "", kod)
                records.append({"kod": kod, "adi": adi})
    return pd.DataFrame(records).drop_duplicates()

# Şablon işlemleri sadece giriş yapanlara açık
if st.session_state["is_logged_in"]:
    st.markdown("---")
    st.subheader("🔖 Tedarikçi Şablon Yönetimi")
    supplier_name = st.text_input("Tedarikçi Adı (şablon için)")
    prefix = st.text_input("Ön Ek Kaldır (Regex)", "^XYZ")
    suffix = st.text_input("Son Ek Kaldır (Regex)", "-TR$")

    if st.button("💾 Şablonu Kaydet"):
        save_supplier_pattern(supplier_name, {"remove_prefix": prefix, "remove_suffix": suffix})
        st.success(f"✅ {supplier_name} için şablon kaydedildi.")

    if st.checkbox("📂 Kayıtlı Şablonları Görüntüle"):
        patterns = load_supplier_patterns()
        if patterns:
            st.json(patterns)
            json_str = json.dumps(patterns, indent=2, ensure_ascii=False)
            st.download_button("📥 JSON Olarak İndir", json_str, file_name="supplier_patterns.json")
        else:
            st.info("Kayıtlı şablon yok.")
# 🔍 Karşılaştırma ve eşleştirme
if u_order and u_invoice:
    order_xml = convert_to_xml(u_order)
    invoice_xml = convert_to_xml(u_invoice)

    if order_xml and invoice_xml:
        df_siparis = extract_items(order_xml).head(5000)
        df_fatura = extract_items(invoice_xml, supplier_name if st.session_state["is_logged_in"] else None).head(5000)

        st.subheader("📦 Sipariş Verileri")
        st.dataframe(df_siparis)

        st.subheader("🧾 Fatura Verileri")
        st.dataframe(df_fatura)

        st.info("🔄 Eşleştirme işlemi başlatılıyor...")
        results = []
        sip_kodlar = df_siparis["kod"].tolist()
        sip_adlar = df_siparis["adi"].tolist()
        norm_kodlar = [normalize_code(k) for k in sip_kodlar]
        norm_adlar = [normalize_name(a) for a in sip_adlar]

        for _, f_row in df_fatura.iterrows():
            f_kod_norm = normalize_code(f_row["kod"])
            kod_eslesme = process.extractOne(f_kod_norm, norm_kodlar, scorer=fuzz.ratio)
            kod_score, name_score, idx = 0, 0, None
            if kod_eslesme:
                _, kod_score, idx = kod_eslesme
            if f_row["adi"]:
                f_ad_norm = normalize_name(f_row["adi"])
                ad_eslesme = process.extractOne(f_ad_norm, norm_adlar, scorer=fuzz.partial_ratio)
                if ad_eslesme:
                    _, name_score, idx2 = ad_eslesme
                    combined_score = w_code * kod_score + w_name * name_score
                    if combined_score > kod_score:
                        idx = idx2
                        kod_score = combined_score

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

        st.success("✅ Eşleştirme tamamlandı.")
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

        dosya_adi = f"eslestirme_{supplier_name if supplier_name else 'cikti'}.xlsx"
        excel_data = to_excel(df_eslesen, df_eslesmeyen)
        st.download_button("📥 Excel İndir", data=excel_data, file_name=dosya_adi)

