import streamlit as st
import pandas as pd
import re
from rapidfuzz import process, fuzz
from io import BytesIO
from lxml import etree
import json
import os

st.set_page_config(layout="wide")
st.title("📦 XML Ürün Eşleştirme Sistemi + Tedarikçi Öğrenme")

threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
w_code = st.slider("📊 Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
w_name = 1 - w_code

u_order = st.file_uploader("📤 Sipariş XML Dosyasını Yükleyin", type="xml")
u_invoice = st.file_uploader("📤 Fatura XML Dosyasını Yükleyin", type="xml")

# Eşleşme seviyesi ikonları
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

# Eşleşmeme seviyesi ikonları
def eslesmeme_seviyesi(puan):
    if puan <= 20:
        return "⚪ Şüpheli eşleşmeme, dikkatli kontrol"
    elif puan <= 34:
        return "🔵 Şüpheli, kontrol edilmeli"
    else:
        return "⚫ Muhtemelen farklı ürün"

# Açıklama kutusu
with st.expander("ℹ️ Eşleşme / Eşleşmeme Seviyesi Açıklamaları"):
    st.markdown("""
    #### ✅ Eşleşen Veriler:
    - 🟢 **%97–100** → Mükemmel
    - 🟡 **%90–96** → Çok İyi
    - 🟠 **%80–89** → İyi
    - 🔴 **%65–79** → Zayıf
    - ⚫ **%0–64** → Farklı Ürün

    #### ❌ Eşleşmeyen Veriler:
    - ⚪ **%0–20** → Şüpheli eşleşmeme, dikkatli kontrol
    - 🔵 **%21–34** → Şüpheli, kontrol edilmeli
    - ⚫ **%35–100** → Muhtemelen farklı ürün
    """)

# Tedarikçi şablonları yükle
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
    df_siparis = extract_items(u_order).head(5000)
    df_fatura = extract_items(u_invoice, supplier_name).head(5000)

    st.subheader("📦 Sipariş Verileri (İlk 5000)")
    st.dataframe(df_siparis)

    st.subheader("🧾 Fatura Verileri (İlk 5000)")
    st.dataframe(df_fatura)

    with st.spinner("🔄 Eşleştirme işlemi yapılıyor..."):
        results = []
        siparis_kodlar = df_siparis["kod"].tolist()
        siparis_adlar = df_siparis["adi"].tolist()

        for _, f_row in df_fatura.iterrows():
            kod_eslesme = process.extractOne(f_row["kod"], siparis_kodlar, scorer=fuzz.ratio)
            kod_score, name_score, idx = 0, 0, None

            if kod_eslesme:
                best_kod, kod_score, idx = kod_eslesme

            if f_row["adi"]:
                name_eslesme = process.extractOne(f_row["adi"], siparis_adlar, scorer=fuzz.partial_ratio)
                if name_eslesme:
                    best_name, name_score, idx2 = name_eslesme
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

        df_result = pd.DataFrame(results)
        df_result = df_result.sort_values(by="Eşleşme Oranı (%)", ascending=False)

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




