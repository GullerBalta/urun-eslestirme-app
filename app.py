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

# Giriş durumu kontrolü
if "giris_yapildi" not in st.session_state:
    st.session_state.giris_yapildi = False

# Giriş yapma kutusu (sadece tedarikçi şablonları için)
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

# Benzerlik ayarları
threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
w_code = st.slider("📊 Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
w_name = 1 - w_code

# Dosya yükleme alanları
u_order = st.file_uploader("📤 Sipariş Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])
u_invoice = st.file_uploader("📤 Fatura Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])

# Tedarikçi bilgisi
supplier_name = st.text_input("🔖 Tedarikçi Adı (şablon tanımlamak için)")
# 🔧 Kayıtlı şablonları yükleyen fonksiyon
def load_supplier_patterns():
    if os.path.exists("supplier_patterns.json"):
        with open("supplier_patterns.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# 🔧 Kod normalize etme (temizlik ve sadeleştirme)
def normalize_code(code):
    if not isinstance(code, str):
        code = str(code)
    code = code.upper()
    code = re.sub(r'[^\w]', '', code)  # harf-sayı dışındaki her şeyi sil
    code = code.lstrip("0")  # baştaki sıfırları sil
    return code

# 🔧 Tedarikçiye özel normalizasyon uygula (regex ile)
def apply_supplier_patterns(code, supplier_name):
    patterns = load_supplier_patterns()
    if supplier_name in patterns:
        prefix_pattern = patterns[supplier_name].get("remove_prefix", "")
        suffix_pattern = patterns[supplier_name].get("remove_suffix", "")
        if prefix_pattern:
            code = re.sub(prefix_pattern, "", code)
        if suffix_pattern:
            code = re.sub(suffix_pattern, "", code)
    return code

# 🔧 Otomatik kolon algılayıcı
def detect_columns(df):
    df_columns = df.columns.str.lower()
    code_col = None
    name_col = None

    for col in df.columns:
        if re.search(r"\bkod|\bcode", col.lower()):
            code_col = col
        elif re.search(r"\badi|\badı|\bname", col.lower()):
            name_col = col

    if not code_col:
        code_col = df.columns[0]  # yedek olarak ilk sütun
    if not name_col and len(df.columns) > 1:
        name_col = df.columns[1]  # yedek olarak ikinci sütun
    return code_col, name_col
# 🔄 Dosyayı DataFrame'e çevir
def convert_file(uploaded_file):
    if uploaded_file is None:
        return None
    try:
        if uploaded_file.name.endswith(".xml"):
            tree = etree.parse(uploaded_file)
            root = tree.getroot()
            data = []

            for elem in root.iter():
                if elem.text and elem.text.strip():
                    text = elem.text.strip()
                    if len(text) > 2:
                        data.append(text)
            df = pd.DataFrame(data, columns=["HamVeri"])
            return df
        elif uploaded_file.name.endswith(".csv"):
            return pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith((".xls", ".xlsx")):
            return pd.read_excel(uploaded_file)
        elif uploaded_file.name.endswith(".txt"):
            return pd.read_csv(uploaded_file, delimiter="\t")
    except Exception as e:
        st.error(f"📛 Dosya okuma hatası: {str(e)}")
        return None

# 🔎 Ürün bilgilerini ayıkla
def extract_items(df, supplier_name):
    if df is None or df.empty:
        return pd.DataFrame()

    if "HamVeri" in df.columns:
        code_pattern = re.compile(r'\b[\w\-\.]{3,}\b')
        records = []
        for text in df["HamVeri"]:
            codes = code_pattern.findall(text)
            for code in codes:
                clean_code = normalize_code(apply_supplier_patterns(code, supplier_name))
                records.append({"urun_kodu": clean_code, "tam_metin": text})
        return pd.DataFrame(records)

    else:
        code_col, name_col = detect_columns(df)
        df = df.fillna("")
        df["urun_kodu"] = df[code_col].astype(str).apply(lambda x: normalize_code(apply_supplier_patterns(x, supplier_name)))
        df["urun_adi"] = df[name_col].astype(str)
        return df[["urun_kodu", "urun_adi"]]

# 🔁 Karşılaştırma işlemi
def match_items(df_fatura, df_siparis, threshold, w_code, w_name):
    results = []

    for _, f_row in df_fatura.iterrows():
        best_match = None
        best_score = 0

        for _, s_row in df_siparis.iterrows():
            code_score = fuzz.ratio(f_row["urun_kodu"], s_row["urun_kodu"])
            name_score = fuzz.ratio(str(f_row.get("urun_adi", "")), str(s_row.get("urun_adi", "")))
            combined_score = (w_code * code_score) + (w_name * name_score)

            if combined_score > best_score:
                best_score = combined_score
                best_match = s_row

        durum = "EŞLEŞTİ" if best_score >= threshold else "EŞLEŞMEDİ"
        seviye = (
            "🟢 Mükemmel" if best_score >= 97 else
            "🟡 Çok İyi" if best_score >= 90 else
            "🟠 Orta" if best_score >= 80 else
            "🔴 Zayıf"
        )

        results.append({
            "Fatura Kodu": f_row["urun_kodu"],
            "Fatura Adı": f_row.get("urun_adi", ""),
            "Sipariş Kodu": best_match["urun_kodu"] if best_match is not None else "",
            "Sipariş Adı": best_match.get("urun_adi", "") if best_match is not None else "",
            "Eşleşme Oranı (%)": round(best_score, 1),
            "Durum": durum,
            "Seviye": seviye
        })

    return pd.DataFrame(results).sort_values(by="Eşleşme Oranı (%)", ascending=False)
converted_order = convert_file(u_order)
converted_invoice = convert_file(u_invoice)

if converted_order is not None:
    df_siparis = extract_items(converted_order, supplier_name).head(5000)
    st.subheader("📦 Sipariş Verileri (İlk 5000)")
    st.dataframe(df_siparis)
else:
    df_siparis = None

if converted_invoice is not None:
    df_fatura = extract_items(converted_invoice, supplier_name).head(5000)
    st.subheader("🧾 Fatura Verileri (İlk 5000)")
    st.dataframe(df_fatura)
else:
    df_fatura = None

if df_siparis is not None and df_fatura is not None and not df_siparis.empty and not df_fatura.empty:
    with st.spinner("🔍 Eşleştiriliyor..."):
        df_result = match_items(df_fatura, df_siparis, threshold, w_code, w_name)
    st.subheader("✅ Eşleşme Sonuçları")
    st.dataframe(df_result)

    # 📥 Excel indir
    dosya_adi = f"eslestirme_{supplier_name if supplier_name else 'cikti'}.xlsx"
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_result.to_excel(writer, sheet_name="Eslestirme", index=False)
        df_siparis.to_excel(writer, sheet_name="Siparis", index=False)
        df_fatura.to_excel(writer, sheet_name="Fatura", index=False)
    buffer.seek(0)

    st.download_button(
        label="📥 Sonuçları Excel Olarak İndir",
        data=buffer,
        file_name=dosya_adi,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.warning("⚠️ Hiçbir eşleşme yapılamadı. Dosyalarınızı kontrol edin.")
