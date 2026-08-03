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

# ----------------- 2. Session State Management -----------------
if 'fabric' not in st.session_state: st.session_state.fabric = ""
if 'shade' not in st.session_state: st.session_state.shade = ""
if 'pc_no' not in st.session_state: st.session_state.pc_no = ""
if 'lot_no' not in st.session_state: st.session_state.lot_no = ""
if 'metres' not in st.session_state: st.session_state.metres = ""
if 'weight' not in st.session_state: st.session_state.weight = ""
if 'last_img_bytes_hash' not in st.session_state: st.session_state.last_img_bytes_hash = None

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
            raw_text = raw_text.replace("```", "").strip()

        return json.loads(raw_text)

    except Exception as err:
        error_msg = str(err).encode('ascii', 'ignore').decode('ascii')
        st.error(f"Error parsing image: {error_msg}")
        return None

# Export Inventory to Excel
def export_inventory_to_excel_with_images():
    conn = sqlite3.connect('warehouse_system.db')
    df = pd.read_sql_query("SELECT roll_id, supplier_name, fabric_name, color_shade, pc_no, lot_no, metres, weight_kg, image_path, status, date_added FROM inventory", conn)
    conn.close()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventory"
    
    headers = ["Roll ID", "Supplier", "Fabric Name", "Color / Shade", "Roll/PC No", "Lot No", "Metres", "Weight (KG)", "Ref# Picture", "Status", "Date Added"]
    ws.append(headers)
    
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = openpyxl.styles.Font(bold=True, color="FFFFFF")
        cell.fill = openpyxl.styles.PatternFill(start_color="1E88E5", end_color="1E88E5", fill_type="solid")
        cell.alignment = openpyxl.styles.Alignment(horizontal="center", vertical="center")
        
    ws.row_dimensions[1].height = 25
    
    for idx, row in df.iterrows():
        row_num = idx + 2
        ws.row_dimensions[row_num].height = 65
        
        ws.cell(row=row_num, column=1, value=row['roll_id'])
        ws.cell(row=row_num, column=2, value=row['supplier_name'])
        ws.cell(row=row_num, column=3, value=row['fabric_name'])
        ws.cell(row=row_num, column=4, value=row['color_shade'])
        ws.cell(row=row_num, column=5, value=str(row['pc_no']))
        ws.cell(row=row_num, column=6, value=str(row['lot_no']))
        ws.cell(row=row_num, column=7, value=row['metres'])
        ws.cell(row=row_num, column=8, value=row['weight_kg'])
        ws.cell(row=row_num, column=10, value=row['status'])
        ws.cell(row=row_num, column=11, value=str(row['date_added']))
        
        img_path = row['image_path']
        if img_path and os.path.exists(img_path):
            try:
                img = Image.open(img_path)
                img.thumbnail((80, 80))
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                
                xl_img = OpenpyxlImage(img_byte_arr)
                xl_img.width = 75
                xl_img.height = 75
                ws.add_image(xl_img, f"I{row_num}")
            except Exception:
                ws.cell(row=row_num, column=9, value="N/A")
        else:
            ws.cell(row=row_num, column=9, value="No Image")

    for col in ws.columns:
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = 16 if col_letter == 'I' else 18

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

# ----------------- 3. UI Setup -----------------
st.set_page_config(page_title="Fabric Tracking System", page_icon="🧵", layout="centered")

# CSS to optimize layout and attempt back-camera preference on mobile browsers
st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3.2em; font-weight: bold; font-size: 16px; }
    .main-title { text-align: center; color: #1E88E5; font-size: 22px; font-weight: bold; margin-bottom: 10px; }
    /* Video stream mirror fix for back camera view */
    video { transform: scaleX(1) !important; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🧵 Fabric Warehouse Tracking</div>', unsafe_allow_html=True)

menu = st.sidebar.radio("Main Menu", [
    "📸 Stock-In (Capture Roll)", 
    "➖ Stock-Out (Dispatch Roll)", 
    "🏢 Manage Suppliers", 
    "📊 Inventory Sheet & Excel"
])

conn = sqlite3.connect('warehouse_system.db')

# --- 1️⃣ Stock-In Page ---
if menu == "📸 Stock-In (Capture Roll)":
    suppliers_df = pd.read_sql_query("SELECT supplier_name FROM suppliers", conn)
    supplier_list = suppliers_df['supplier_name'].tolist() if not suppliers_df.empty else ['El-basha']
    selected_supplier = st.selectbox("Select Supplier:", supplier_list)
    
    source_type = st.radio("Capture Method:", ["📸 Camera", "📁 Gallery Upload"], horizontal=True)
    
    img_file = None
    if "📸 Camera" in source_type:
        # st.camera_input natively triggers standard system camera dialog on phones
        img_file = st.camera_input("Take Roll Tag Photo")
    else:
        img_file = st.file_uploader("Upload Image", type=["jpg", "png", "jpeg", "webp"])

    img_saved_path = ""

    # Automatic execution upon receiving new image
    if img_file is not None:
        image_bytes = img_file.getvalue()
        current_hash = hash(image_bytes)

        # Execute OCR automatically only if image changed
        if st.session_state.last_img_bytes_hash != current_hash:
            with st.spinner("🤖 Auto-processing tag image with Gemini OCR..."):
                extracted = parse_card_with_gemini(image_bytes)
                if extracted:
                    st.session_state.fabric = str(extracted.get("fabric", ""))
                    st.session_state.shade = str(extracted.get("shade", ""))
                    st.session_state.pc_no = str(extracted.get("pc_no", ""))
                    st.session_state.lot_no = str(extracted.get("lot_no", ""))
                    st.session_state.metres = str(extracted.get("metres", ""))
                    st.session_state.weight = str(extracted.get("weight", ""))
                    st.session_state.last_img_bytes_hash = current_hash
                    st.rerun()

        st.image(image_bytes, caption="Captured Tag Preview", use_column_width=True)

        temp_img_name = f"roll_{selected_supplier}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.png"
        img_saved_path = os.path.join('roll_images', temp_img_name)
        with open(img_saved_path, 'wb') as f:
            f.write(image_bytes)

    st.markdown("### 📝 Confirm Roll Specifications")
    
    # Text inputs populated directly from st.session_state
    fabric_name = st.text_input("Fabric Name", value=st.session_state.fabric)
    color_shade = st.text_input("Color / Shade", value=st.session_state.shade)
    
    c1, c2 = st.columns(2)
    with c1:
        pc_no_input = st.text_input("Roll / PC No.", value=st.session_state.pc_no)
        metres_input = st.text_input("Metres / Length", value=st.session_state.metres)
    with c2:
        lot_no_input = st.text_input("Lot No.", value=st.session_state.lot_no)
        weight_input = st.text_input("Weight (KGs)", value=st.session_state.weight)
        
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("✅ Confirm & Save Roll to Inventory"):
        pc_str = pc_no_input.strip() if pc_no_input else "0"
        lot_str = lot_no_input.strip() if lot_no_input else "0"
        
        time_tag = pd.Timestamp.now().strftime('%M%S')
        roll_id = f"ROLL-{selected_supplier[:3].upper()}-P{pc_str}-L{lot_str}-{time_tag}"
        
        try:
            metres = float(metres_input) if metres_input else 0.0
            weight_kg = float(weight_input) if weight_input else 0.0
            
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO inventory (roll_id, supplier_name, fabric_name, color_shade, pc_no, lot_no, metres, weight_kg, image_path, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'IN_STOCK')
            ''', (roll_id, selected_supplier, fabric_name, color_shade, pc_str, lot_str, metres, weight_kg, img_saved_path))
            conn.commit()
            
            # Reset form state
            st.session_state.fabric = ""
            st.session_state.shade = ""
            st.session_state.pc_no = ""
            st.session_state.lot_no = ""
            st.session_state.metres = ""
            st.session_state.weight = ""
            st.session_state.last_img_bytes_hash = None
            
            st.balloons()
            st.success(f"Saved Successfully! Roll ID: ({roll_id})")
        except Exception as e:
            st.error(f"Save error: {e}")

# --- 2️⃣ Stock-Out Page ---
elif menu == "➖ Stock-Out (Dispatch Roll)":
    st.subheader("Dispatch Roll")
    stock_df = pd.read_sql_query("SELECT roll_id, supplier_name, fabric_name, color_shade, metres FROM inventory WHERE status='IN_STOCK'", conn)
    
    if stock_df.empty:
        st.info("No rolls currently available in stock.")
    else:
        selected_roll = st.selectbox("Select Roll ID:", stock_df['roll_id'].tolist())
        roll_details = stock_df[stock_df['roll_id'] == selected_roll].iloc[0]
        st.warning(f"Details: {roll_details['fabric_name']} | Color: {roll_details['color_shade']} | {roll_details['metres']} Metres")
        
        if st.button("Confirm Dispatch"):
            cursor = conn.cursor()
            cursor.execute("UPDATE inventory SET status='DISPATCHED' WHERE roll_id=?", (selected_roll,))
            conn.commit()
            st.success(f"Roll {selected_roll} dispatched successfully!")

# --- 3️⃣ Manage Suppliers Page ---
elif menu == "🏢 Manage Suppliers":
    st.subheader("Add New Supplier")
    with st.form("add_supplier"):
        sup_name = st.text_input("Supplier Name")
        sup_desc = st.text_area("Notes")
        save_sup = st.form_submit_button("Save Supplier")
        if save_sup and sup_name:
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO suppliers (supplier_name, description) VALUES (?, ?)", (sup_name, sup_desc))
                conn.commit()
                st.success(f"Supplier '{sup_name}' added!")
            except:
                st.error("Supplier exists!")
                
    st.dataframe(pd.read_sql_query("SELECT supplier_name AS 'Supplier Name', description AS 'Notes' FROM suppliers", conn), use_container_width=True)

# --- 4️⃣ Inventory Sheet Page ---
elif menu == "📊 Inventory Sheet & Excel":
    st.subheader("Warehouse Inventory & Export")
    
    excel_data = export_inventory_to_excel_with_images()
    st.download_button(
        label="📥 Download Excel File (With Embedded Pictures)",
        data=excel_data,
        file_name=f"Warehouse_Inventory_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.markdown("---")
    df = pd.read_sql_query("SELECT roll_id AS 'Roll ID', supplier_name AS 'Supplier', fabric_name AS 'Fabric', color_shade AS 'Color', pc_no AS 'Roll No', lot_no AS 'Lot', metres AS 'Meters', weight_kg AS 'Weight KG', status AS 'Status' FROM inventory", conn)
    st.dataframe(df, use_container_width=True)

conn.close()
