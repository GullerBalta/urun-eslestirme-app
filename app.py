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
        return "⚪ Şüpheli eşleşmeme, dikkatli kontrol"
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
    return re.sub(r'[^A-Za-z0-9]', '', str(code))

def normalize_name(name):
    name = str(name).lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def load_learned_matches():
    if os.path.exists("learned_matches.json"):
        with open("learned_matches.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_learned_match(fatura_kodu, siparis_kodu, fatura_adi, siparis_adi):
    matches = load_learned_matches()
    matches[fatura_kodu] = {
        "siparis_kodu": siparis_kodu,
        "fatura_adi": fatura_adi,
        "siparis_adi": siparis_adi
    }
    with open("learned_matches.json", "w", encoding="utf-8") as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)

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
                if supplier_pattern:
                    kod = re.sub(supplier_pattern.get("remove_prefix", "^$"), "", kod)
                    kod = re.sub(supplier_pattern.get("remove_suffix", "$^"), "", kod)
                records.append({"kod": kod, "adi": adi})
    return pd.DataFrame(records).drop_duplicates(subset=["kod", "adi"])

supplier_name = st.text_input("🔖 Tedarikçi Adı (şablon tanımlamak için)")
prefix = st.text_input("Ön Ek Kaldır (Regex)", "^XYZ")
suffix = st.text_input("Son Ek Kaldır (Regex)", "-TR$")

if st.button("💡 Bu tedarikçiye özel şablonu kaydet"):
    save_supplier_pattern(supplier_name, {"remove_prefix": prefix, "remove_suffix": suffix})
    st.success(f"✅ '{supplier_name}' için şablon kaydedildi.")

if u_order and u_invoice:
    converted_order = convert_to_xml(u_order)
    converted_invoice = convert_to_xml(u_invoice)

    if converted_order and converted_invoice:
        df_siparis = extract_items(converted_order).head(5000)
        df_fatura = extract_items(converted_invoice, supplier_name).head(5000)

        st.subheader("📦 Sipariş Verileri (İlk 5000)")
        st.dataframe(df_siparis)

        st.subheader("🧾 Fatura Verileri (İlk 5000)")
        st.dataframe(df_fatura)

        with st.spinner("🔄 Eşleştirme işlemi yapılıyor..."):
            results = []
            siparis_kodlar = df_siparis["kod"].tolist()
            siparis_adlar = df_siparis["adi"].tolist()

            normalized_siparis_kodlar = [normalize_code(k) for k in siparis_kodlar]
            normalized_siparis_adlar = [normalize_name(ad) for ad in siparis_adlar]

            learned = load_learned_matches()

            for _, f_row in df_fatura.iterrows():
                f_kod_norm = normalize_code(f_row["kod"])
                f_name_norm = normalize_name(f_row["adi"])

                # 👇 Eğer daha önce eşleştirilmişse direkt yükle
                if f_row["kod"] in learned:
                    matched = learned[f_row["kod"]]
                    kod_score = 100
                    durum = "ÖĞRENİLDİ"
                    results.append({
                        "Fatura Kodu": f_row["kod"],
                        "Fatura Adı": f_row["adi"],
                        "Sipariş Kodu": matched["siparis_kodu"],
                        "Sipariş Adı": matched["siparis_adi"],
                        "Eşleşme Oranı (%)": 100.0,
                        "Durum": durum
                    })
                    continue

                kod_score, name_score, idx = 0, 0, None
                kod_eslesme = process.extractOne(f_kod_norm, normalized_siparis_kodlar, scorer=fuzz.ratio)
                if kod_eslesme:
                    _, kod_score, idx = kod_eslesme

                if f_row["adi"]:
                    name_eslesme = process.extractOne(f_name_norm, normalized_siparis_adlar, scorer=fuzz.partial_ratio)
                    if name_eslesme:
                        _, name_score, idx2 = name_eslesme
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

                if durum == "EŞLEŞTİ":
                    save_learned_match(f_row["kod"], matched["kod"], f_row["adi"], matched["adi"])

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



