import os
import io
import json
import sqlite3
import pandas as pd
import streamlit as st
from PIL import Image
import openpyxl
from openpyxl.drawing.image import Image as OpenpyxlImage
from google import genai
from google.genai import types

# ----------------- 1. Database Initialization -----------------
def init_db():
    conn = sqlite3.connect('warehouse_system.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_name TEXT UNIQUE NOT NULL,
        description TEXT
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inventory (
        roll_id TEXT PRIMARY KEY,
        supplier_name TEXT,
        fabric_name TEXT,
        color_shade TEXT,
        pc_no TEXT,
        lot_no TEXT,
        metres REAL,
        weight_kg REAL,
        image_path TEXT,
        status TEXT DEFAULT 'IN_STOCK',
        date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cursor.execute("INSERT OR IGNORE INTO suppliers (supplier_name, description) VALUES ('El-basha', 'Standard Tag')")
    conn.commit()
    conn.close()

init_db()

if not os.path.exists('roll_images'):
    os.makedirs('roll_images')

# ----------------- 2. Session State Initialization -----------------
for key in ['fabric', 'shade', 'pc_no', 'lot_no', 'metres', 'weight']:
    if key not in st.session_state:
        st.session_state[key] = ""

if 'last_processed_img' not in st.session_state:
    st.session_state.last_processed_img = None

# Gemini OCR Function
def parse_card_with_gemini(image_bytes):
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            st.error("Missing GEMINI_API_KEY in Streamlit Secrets!")
            return None

        client = genai.Client(api_key=api_key)

        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/jpeg"
        )

        prompt_text = (
            "Analyze this fabric card image and extract values for these fields:\n"
            "- fabric: Fabric Name\n"
            "- shade: Color or Shade\n"
            "- pc_no: Roll or PC Number\n"
            "- lot_no: Lot Number\n"
            "- metres: Length or Meters\n"
            "- weight: Weight in KGs\n\n"
            "Respond ONLY with a valid raw JSON object with keys: fabric, shade, pc_no, lot_no, metres, weight."
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image_part, prompt_text]
        )

        raw_text = response.text.strip() if response and response.text else ""
        if raw_text.startswith("```json"):
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text.replace("
