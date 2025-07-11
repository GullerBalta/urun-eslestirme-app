import streamlit as st
import pandas as pd
import re
from rapidfuzz import process, fuzz
from io import BytesIO
from lxml import etree
import json
import os

st.set_page_config(layout="wide")
st.title("📦 XML Ürün Eşleştirme Sistemi + Tedarikçi Öğrenme (İlk 5000 Kayıt)")

# Eşik ve ağırlık ayarları
threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
w_code = st.slider("📊 Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
w_name = 1 - w_code

# Dosya yükleyiciler
u_order = st.file_uploader("📤 Sipariş XML Dosyasını Yükleyin", type="xml")
u_invoice = st.file_uploader("📤 Fatura XML Dosyasını Yükleyin", type="xml")

# Tedarikçi şablonlarını yükle
def load_supplier_patterns():
    if os.path.exists("supplier_patterns.json"):
        with open("supplier_patterns.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Tedarikçi şablonu kaydet
def save_supplier_pattern(name, pattern):
    patterns = load_supplier_patterns()
    patterns[name] = pattern
    with open("supplier_patterns.json", "w", encoding="utf-8") as f:
        json.dump(patterns, f, indent=2, ensure_ascii=False)

# XML'den ürün kod ve adını çıkar
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

# Tedarikçi adı girişi
supplier_name = st.text_input("Tedarikçi Adı (şablon tanımlamak için)")
prefix = st.text_input("Ön Ek Kaldır (Regex)", "^XYZ")
suffix = st.text_input("Son Ek Kaldır (Regex)", "-TR$")

if st.button("💡 Bu tedarikçiye özel şablonu kaydet"):
    save_supplier_pattern(supplier_name, {"remove_prefix": prefix, "remove_suffix": suffix})
    st.success(f"'{supplier_name}' için şablon kaydedildi.")

# XML dosyaları yüklendiyse işleme başla
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

            if idx is not None and kod_score >= threshold:
                matched = df_siparis.iloc[idx]
                status = "EŞLEŞTİ"
            else:
                matched = {"kod": "", "adi": ""}
                status = "EŞLEŞMEDİ"

            results.append({
                "Fatura Kodu": f_row["kod"],
                "Fatura Adı": f_row["adi"],
                "Sipariş Kodu": matched["kod"],
                "Sipariş Adı": matched["adi"],
                "Eşleşme Oranı (%)": round(kod_score, 1),
                "Durum": status
            })

        df_result = pd.DataFrame(results)
        df_eslesen = df_result[df_result["Durum"] == "EŞLEŞTİ"].reset_index(drop=True)
        df_eslesmeyen = df_result[df_result["Durum"] == "EŞLEŞMEDİ"].reset_index(drop=True)

    st.success("✅ Eşleştirme tamamlandı!")
    st.subheader("✅ Eşleşen Kayıtlar")
    st.dataframe(df_eslesen)

    st.subheader("❌ Eşleşmeyen Kayıtlar")
    st.dataframe(df_eslesmeyen)

    # Excel çıktısı
    def to_excel(df1, df2):
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df1.to_excel(writer, sheet_name="Eslesen", index=False)
            df2.to_excel(writer, sheet_name="Eslesmeyen", index=False)
        return out.getvalue()

    excel_data = to_excel(df_eslesen, df_eslesmeyen)
    st.download_button("📥 Excel İndir", data=excel_data, file_name="eslestirme_sonuclari.xlsx")




