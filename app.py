import streamlit as st
import pandas as pd
import re
from rapidfuzz import process, fuzz
from io import BytesIO
from lxml import etree
import sqlite3
import os

# Veritabanını başlat

def init_db():
    conn = sqlite3.connect("matches.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learned_matches (
            fatura_kodu TEXT PRIMARY KEY,
            siparis_kodu TEXT,
            fatura_adi TEXT,
            siparis_adi TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ... (geri kalan kod yukarıdaki gibi entegre edilmiştir)




