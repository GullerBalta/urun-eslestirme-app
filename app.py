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

# Oturum yönetimi
if "giris_yapildi" not in st.session_state:
    st.session_state.giris_yapildi = False

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

# Benzerlik eşiği ve ağırlık ayarları
threshold = st.slider("🔧 Benzerlik Eşiği (%)", 50, 100, 90)
w_code = st.slider("📊 Ürün Kodu Ağırlığı (%)", 0, 100, 80) / 100.0
w_name = 1 - w_code

# Dosya yükleme
u_order = st.file_uploader("📤 Sipariş Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])
u_invoice = st.file_uploader("📤 Fatura Dosyasını Yükleyin", type=["xml", "csv", "xls", "xlsx", "txt"])

# Tedarikçi adı
supplier_name = st.text_input("🔖 Tedarikçi Adı (şablon tanımlamak için)")
# Temizleme: Küçült, boşlukları sil, özel karakterleri kaldır
def normalize_code(code):
    if pd.isna(code):
        return ""
    return re.sub(r"[^\w]", "", str(code)).lstrip("0").lower()

def normalize_name(name):
    if pd.isna(name):
        return ""
    return re.sub(r"\s+", " ", str(name)).strip().lower()

# Kolon isimlerini standartlaştır
def clean_column_name(col):
    return re.sub(r"[^\w]", "", col).lower()

# Tedarikçi desenlerini JSON’dan yükle
def load_supplier_patterns():
    if os.path.exists("supplier_patterns.json"):
        with open("supplier_patterns.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Kodun başından ve sonundan tedarikçiye özel ekleri kaldır
def apply_supplier_patterns(code, supplier_name):
    patterns = load_supplier_patterns()
    original_code = str(code)
    if supplier_name in patterns:
        remove_prefix = patterns[supplier_name].get("remove_prefix", "")
        remove_suffix = patterns[supplier_name].get("remove_suffix", "")
        if remove_prefix:
            original_code = re.sub(remove_prefix, "", original_code)
        if remove_suffix:
            original_code = re.sub(remove_suffix, "", original_code)
    return normalize_code(original_code)

# XML dışındaki dosyalarda kolonları otomatik tanı
def extract_items(df, supplier_name):
    df = df.copy()
    df.columns = [clean_column_name(col) for col in df.columns]
    kod_col = None
    ad_col = None

    for col in df.columns:
        if not kod_col and re.search(r"(kod|code|ürün.*no|partnumber)", col, re.IGNORECASE):
            kod_col = col
        if not ad_col and re.search(r"(ad|isim|name|ürün.*ad)", col, re.IGNORECASE):
            ad_col = col

    if not kod_col:
        st.error("❗ Ürün kodu kolonu tespit edilemedi.")
        return pd.DataFrame()

    if ad_col:
        return df[[kod_col, ad_col]].rename(columns={kod_col: "kod", ad_col: "adi"})
    else:
        return df[[kod_col]].rename(columns={kod_col: "kod"}).assign(adi="")
if u_order and u_invoice:
    try:
        df_order = pd.read_excel(u_order) if u_order.name.endswith(("xls", "xlsx")) else pd.read_csv(u_order)
        df_invoice = pd.read_excel(u_invoice) if u_invoice.name.endswith(("xls", "xlsx")) else pd.read_csv(u_invoice)

        df_siparis = extract_items(df_order, supplier_name).head(5000)
        df_fatura = extract_items(df_invoice, supplier_name).head(5000)

        st.subheader("🧾 Fatura Verileri (İlk 5000)")
        st.dataframe(df_fatura)

        st.subheader("📦 Sipariş Verileri (İlk 5000)")
        st.dataframe(df_siparis)

        results = []
        for i, row_f in df_fatura.iterrows():
            best_match = None
            best_score = 0
            kod_f, adi_f = str(row_f["kod"]), str(row_f["adi"])

            for j, row_o in df_siparis.iterrows():
                kod_o, adi_o = str(row_o["kod"]), str(row_o["adi"])

                k_f = apply_supplier_patterns(kod_f, supplier_name)
                k_o = apply_supplier_patterns(kod_o, supplier_name)

                sim_kod = fuzz.ratio(k_f, k_o)
                sim_ad = fuzz.ratio(normalize_name(adi_f), normalize_name(adi_o)) if adi_f and adi_o else 0
                toplam = (sim_kod * w_code + sim_ad * w_name)

                if toplam > best_score:
                    best_score = toplam
                    best_match = row_o

            durum = "EŞLEŞTİ" if best_score >= threshold else "EŞLEŞMEDİ"
            seviye = "🟢 Mükemmel" if best_score >= 97 else "🟡 Çok İyi" if best_score >= 90 else "🔵 Şüpheli" if best_score >= 75 else "⚪ Farklı"
            results.append({
                "Fatura Kodu": kod_f,
                "Fatura Adı": adi_f,
                "Sipariş Kodu": best_match["kod"] if best_match is not None else "",
                "Sipariş Adı": best_match["adi"] if best_match is not None else "",
                "Eşleşme Oranı (%)": round(best_score, 1),
                "Durum": durum,
                "Seviye": seviye
            })

        df_result = pd.DataFrame(results)
        df_result = df_result.sort_values(by="Eşleşme Oranı (%)", ascending=False)

        st.subheader("📊 Eşleşme Sonuçları")
        st.dataframe(df_result)

        dosya_adi = f"eslestirme_{supplier_name if supplier_name else 'cikti'}.xlsx"
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_result.to_excel(writer, index=False, sheet_name="Eşleşme Sonuçları")
        st.download_button("📥 Sonuçları Excel Olarak İndir", data=buffer.getvalue(), file_name=dosya_adi, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except Exception as e:
        st.error(f"❌ Hata oluştu: {str(e)}")

