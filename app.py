import os
import io
import sqlite3
import pandas as pd
import streamlit as st
from PIL import Image
import openpyxl
from openpyxl.drawing.image import Image as OpenpyxlImage
from google import genai

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
    cursor.execute("INSERT OR IGNORE INTO suppliers (supplier_name, description) VALUES ('El-basha', 'FQ-QC-57')")
    conn.commit()
    conn.close()

init_db()

if not os.path.exists('roll_images'):
    os.makedirs('roll_images')

# ----------------- 2. Session State Setup -----------------
if 'card_data' not in st.session_state:
    st.session_state.card_data = {
        "fabric": "",
        "shade": "",
        "pc_no": "",
        "lot_no": "",
        "metres": "",
        "weight": ""
    }
if 'last_img_id' not in st.session_state:
    st.session_state.last_img_id = None

# Gemini OCR Reader Engine
def parse_card_with_gemini(image_bytes):
    data = {"fabric": "", "shade": "", "pc_no": "", "lot_no": "", "metres": "", "weight": ""}
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            return data

        client = genai.Client(api_key=api_key)
        image = Image.open(io.BytesIO(image_bytes))

        # Direct prompt mapped to standard fabric card layouts
        prompt = """
        Analyze this fabric roll tag/label and extract the exact printed text values:
        - Fabric Name (e.g. INTERLOCKP1, Rosetta) -> output as 'Fabric'
        - Color (e.g. TEAL, Black) -> output as 'Shade'
        - Roll No or PC No (e.g. 6) -> output as 'PC'
        - Lot No (e.g. 0209) -> output as 'LOT'
        - Length or Meters (e.g. 88) -> output as 'Metres'
        - NW(KG) or Weight (e.g. 21.1) -> output as 'Weight'

        Respond strictly in this line-by-line format:
        Fabric: <value>
        Shade: <value>
        PC: <value>
        LOT: <value>
        Metres: <value>
        Weight: <value>
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, prompt]
        )
        
        raw_text = response.text if response and response.text else ""
        
        for line in raw_text.splitlines():
            line_clean = line.strip()
            if line_clean.lower().startswith('fabric:'):
                data["fabric"] = line_clean.split(':', 1)[1].strip()
            elif line_clean.lower().startswith('shade:'):
                data["shade"] = line_clean.split(':', 1)[1].strip()
            elif line_clean.lower().startswith('pc:'):
                data["pc_no"] = line_clean.split(':', 1)[1].strip()
            elif line_clean.lower().startswith('lot:'):
                data["lot_no"] = line_clean.split(':', 1)[1].strip()
            elif line_clean.lower().startswith('metres:'):
                data["metres"] = line_clean.split(':', 1)[1].strip()
            elif line_clean.lower().startswith('weight:'):
                data["weight"] = line_clean.split(':', 1)[1].strip()

        return data
    except Exception as err:
        # Prevent ASCII / UTF-8 encoding crashes
        print("Error parsing image:", str(err).encode('ascii', 'ignore').decode('ascii'))
        return data

# Export to Excel with Embedded Images
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

# ----------------- 3. Streamlit Interface (English Default) -----------------
st.set_page_config(page_title="Fabric Warehouse System", page_icon="🧵", layout="centered")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3.2em; font-weight: bold; font-size: 16px; }
    .main-title { text-align: center; color: #1E88E5; font-size: 22px; font-weight: bold; margin-bottom: 10px; }
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

# --- 1️⃣ Stock-In ---
if menu == "📸 Stock-In (Capture Roll)":
    suppliers_df = pd.read_sql_query("SELECT supplier_name FROM suppliers", conn)
    supplier_list = suppliers_df['supplier_name'].tolist() if not suppliers_df.empty else ['El-basha']
    selected_supplier = st.selectbox("Select Supplier:", supplier_list)
    
    source_type = st.radio("Capture Method:", ["📸 Camera", "📁 Gallery Upload"], horizontal=True)
    
    img_file = None
    if "📸 Camera" in source_type:
        img_file = st.camera_input("Take Roll Tag Photo")
    else:
        img_file = st.file_uploader("Upload Image", type=["jpg", "png", "jpeg", "webp"])

    img_saved_path = ""

    if img_file is not None:
        image_bytes = img_file.getvalue()
        current_img_id = hash(image_bytes)
        
        if st.session_state.last_img_id != current_img_id:
            with st.spinner("Analyzing image with Gemini OCR..."):
                extracted = parse_card_with_gemini(image_bytes)
                st.session_state.card_data = extracted
                st.session_state.last_img_id = current_img_id

        st.image(image_bytes, caption="Captured Tag Image", use_column_width=True)
        
        temp_img_name = f"roll_{selected_supplier}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.png"
        img_saved_path = os.path.join('roll_images', temp_img_name)
        with open(img_saved_path, 'wb') as f:
            f.write(image_bytes)

    st.markdown("### 📝 Roll Specifications")
    
    fabric_name = st.text_input("Fabric Name", value=st.session_state.card_data["fabric"], key="input_fabric")
    color_shade = st.text_input("Color / Shade", value=st.session_state.card_data["shade"], key="input_shade")
    
    c1, c2 = st.columns(2)
    with c1:
        pc_no_input = st.text_input("Roll / PC No.", value=st.session_state.card_data["pc_no"], key="input_pc")
        metres_input = st.text_input("Metres / Length", value=st.session_state.card_data["metres"], key="input_metres")
    with c2:
        lot_no_input = st.text_input("Lot No.", value=st.session_state.card_data["lot_no"], key="input_lot")
        weight_input = st.text_input("Weight (KGs)", value=st.session_state.card_data["weight"], key="input_weight")
        
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("✅ Confirm & Save Roll to Warehouse"):
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
            
            st.session_state.card_data = {"fabric": "", "shade": "", "pc_no": "", "lot_no": "", "metres": "", "weight": ""}
            st.session_state.last_img_id = None
            
            st.balloons()
            st.success(f"Roll Saved Successfully! ID: ({roll_id})")
        except Exception as e:
            st.error(f"Error saving roll: {e}")

# --- 2️⃣ Stock-Out ---
elif menu == "➖ Stock-Out (Dispatch Roll)":
    st.subheader("Dispatched Roll")
    stock_df = pd.read_sql_query("SELECT roll_id, supplier_name, fabric_name, color_shade, metres FROM inventory WHERE status='IN_STOCK'", conn)
    
    if stock_df.empty:
        st.info("No rolls currently available in stock.")
    else:
        selected_roll = st.selectbox("Select Roll ID to dispatch:", stock_df['roll_id'].tolist())
        roll_details = stock_df[stock_df['roll_id'] == selected_roll].iloc[0]
        st.warning(f"Details: {roll_details['fabric_name']} | Color: {roll_details['color_shade']} | {roll_details['metres']} Metres")
        
        if st.button("Confirm Dispatch"):
            cursor = conn.cursor()
            cursor.execute("UPDATE inventory SET status='DISPATCHED' WHERE roll_id=?", (selected_roll,))
            conn.commit()
            st.success(f"Roll {selected_roll} dispatched successfully!")

# --- 3️⃣ Manage Suppliers ---
elif menu == "🏢 Manage Suppliers":
    st.subheader("Add New Supplier")
    with st.form("add_supplier"):
        sup_name = st.text_input("Supplier Name", placeholder="e.g. El-basha")
        sup_desc = st.text_area("Notes", placeholder="Optional")
        save_sup = st.form_submit_button("Save Supplier")
        if save_sup and sup_name:
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO suppliers (supplier_name, description) VALUES (?, ?)", (sup_name, sup_desc))
                conn.commit()
                st.success(f"Supplier '{sup_name}' added!")
            except:
                st.error("Supplier already exists!")
                
    st.dataframe(pd.read_sql_query("SELECT supplier_name AS 'Supplier Name', description AS 'Notes' FROM suppliers", conn), use_container_width=True)

# --- 4️⃣ Inventory Sheet ---
elif menu == "📊 Inventory Sheet & Excel":
    st.subheader("Warehouse Inventory & Export")
    
    excel_data = export_inventory_to_excel_with_images()
    st.download_button(
        label="📥 Download Complete Excel (With Pictures)",
        data=excel_data,
        file_name=f"Warehouse_Inventory_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.markdown("---")
    df = pd.read_sql_query("SELECT roll_id AS 'Roll ID', supplier_name AS 'Supplier', fabric_name AS 'Fabric', color_shade AS 'Color', pc_no AS 'Roll No', lot_no AS 'Lot', metres AS 'Meters', weight_kg AS 'Weight KG', status AS 'Status' FROM inventory", conn)
    st.dataframe(df, use_container_width=True)

conn.close()
