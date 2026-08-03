import os
import io
import sqlite3
import pandas as pd
import streamlit as st
from PIL import Image
import openpyxl
from openpyxl.drawing.image import Image as OpenpyxlImage
from google import genai

# ----------------- 1. تهيئة قاعدة البيانات -----------------
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
    cursor.execute("INSERT OR IGNORE INTO suppliers (supplier_name, description) VALUES ('El-basha', 'كارت الباشا FQ-QC-57')")
    conn.commit()
    conn.close()

init_db()

if not os.path.exists('roll_images'):
    os.makedirs('roll_images')

# ----------------- 2. تهيئة الـ Session State -----------------
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

# دالة قراءة الصورة باستخدام Gemini API (مع Prompt بالإنجليزية لتفادي خطأ الترميز ASCII)
def parse_card_with_gemini(image_bytes):
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            st.error("⚠️ GEMINI_API_KEY is missing in Secrets!")
            return {"fabric": "", "shade": "", "pc_no": "", "lot_no": "", "metres": "", "weight": ""}

        client = genai.Client(api_key=api_key)
        image = Image.open(io.BytesIO(image_bytes))

        # Prompt strictly in English to prevent UTF-8 / ASCII encoding issues
        prompt = """
        Read the fabric card image carefully and extract the following details. 
        Note that 'Roll No' corresponds to 'PC', 'Length' corresponds to 'Metres', and 'NW(KG)' or 'GW(KG)' corresponds to 'Weight'.
        Output EXACTLY in this format line by line:
        Fabric: <extracted fabric name>
        Shade: <extracted color or shade>
        PC: <extracted roll or PC number>
        LOT: <extracted lot number>
        Metres: <extracted length or meters>
        Weight: <extracted weight in kg>
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, prompt]
        )
        
        text = response.text or ""
        data = {"fabric": "", "shade": "", "pc_no": "", "lot_no": "", "metres": "", "weight": ""}
        
        for line in text.split('\n'):
            line_str = line.strip()
            if line_str.startswith('Fabric:'): data["fabric"] = line_str.replace('Fabric:', '').strip()
            elif line_str.startswith('Shade:'): data["shade"] = line_str.replace('Shade:', '').strip()
            elif line_str.startswith('PC:'): data["pc_no"] = line_str.replace('PC:', '').strip()
            elif line_str.startswith('LOT:'): data["lot_no"] = line_str.replace('LOT:', '').strip()
            elif line_str.startswith('Metres:'): data["metres"] = line_str.replace('Metres:', '').strip()
            elif line_str.startswith('Weight:'): data["weight"] = line_str.replace('Weight:', '').strip()
            
        return data
    except Exception as e:
        st.error(f"خطأ أثناء قراءة الصورة: {e}")
        return {"fabric": "", "shade": "", "pc_no": "", "lot_no": "", "metres": "", "weight": ""}

# دالة تصدير شيت الإكسل
def export_inventory_to_excel_with_images():
    conn = sqlite3.connect('warehouse_system.db')
    df = pd.read_sql_query("SELECT roll_id, supplier_name, fabric_name, color_shade, pc_no, lot_no, metres, weight_kg, image_path, status, date_added FROM inventory", conn)
    conn.close()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "المخزون الحالي"
    
    headers = ["كود التوب", "المورد", "اسم الخامة", "اللون / الدرجة", "رقم التوب", "اللوت", "الأمتار", "الوزن (كجم)", "Ref# Picture", "الحالة", "تاريخ الإضافة"]
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
                ws.cell(row=row_num, column=9, value="صورة غير متاحة")
        else:
            ws.cell(row=row_num, column=9, value="لا توجد صورة")

    for col in ws.columns:
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = 16 if col_letter == 'I' else 18

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

# ----------------- 3. إعدادات الواجهة -----------------
st.set_page_config(page_title="نظام تتبع الأقمشة", page_icon="🧵", layout="centered")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; font-weight: bold; font-size: 16px; }
    .main-title { text-align: center; color: #1E88E5; font-size: 22px; font-weight: bold; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🧵 إدارة مخزن الأقمشة</div>', unsafe_allow_html=True)

menu = st.sidebar.radio("القائمة الرئيسية", [
    "📸 إضافة توب للمخزن (Stock-In)", 
    "➖ صرف توب (Stock-Out)", 
    "🏢 إضافة/إدارة الموردين", 
    "📊 شيت المخزون والإكسل"
])

conn = sqlite3.connect('warehouse_system.db')

# --- 1️⃣ إضافة توب جديد ---
if menu == "📸 إضافة توب للمخزن (Stock-In)":
    suppliers_df = pd.read_sql_query("SELECT supplier_name FROM suppliers", conn)
    supplier_list = suppliers_df['supplier_name'].tolist() if not suppliers_df.empty else ['El-basha']
    selected_supplier = st.selectbox("🏷️ اختر المورد:", supplier_list)
    
    source_type = st.radio("طريقة التصوير:", ["📸 التقاط صورة مباشرة", "📁 اختيار من المعرض"], horizontal=True)
    
    img_file = None
    if "📸 التقاط صورة" in source_type:
        img_file = st.camera_input("التقط صورة الكارت")
    else:
        img_file = st.file_uploader("اختر الصورة", type=["jpg", "png", "jpeg", "webp"])

    img_saved_path = ""

    if img_file is not None:
        image_bytes = img_file.getvalue()
        current_img_id = hash(image_bytes)
        
        if st.session_state.last_img_id != current_img_id:
            with st.spinner("🤖 جاري قراءة واستخراج بيانات الكارت عبر Gemini..."):
                extracted = parse_card_with_gemini(image_bytes)
                st.session_state.card_data = extracted
                st.session_state.last_img_id = current_img_id
            st.success("✅ تم استخراج البيانات بنجاح!")

        st.image(image_bytes, caption="معاينة كارت التوب الملتقط", use_column_width=True)
        
        temp_img_name = f"roll_{selected_supplier}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.png"
        img_saved_path = os.path.join('roll_images', temp_img_name)
        with open(img_saved_path, 'wb') as f:
            f.write(image_bytes)

    st.markdown("### 📝 بيانات التوب لتأكيد الحفظ")
    
    fabric_name = st.text_input("اسم الخامة (Fabric)", value=st.session_state.card_data["fabric"], key="input_fabric")
    color_shade = st.text_input("اللون / الدرجة (Shade)", value=st.session_state.card_data["shade"], key="input_shade")
    
    c1, c2 = st.columns(2)
    with c1:
        pc_no_input = st.text_input("رقم التوب (PC / Roll NO.)", value=st.session_state.card_data["pc_no"], key="input_pc")
        metres_input = st.text_input("الأمتار (Metres / Length)", value=st.session_state.card_data["metres"], key="input_metres")
    with c2:
        lot_no_input = st.text_input("رقم اللوت (LOT NO.)", value=st.session_state.card_data["lot_no"], key="input_lot")
        weight_input = st.text_input("الوزن (Kgs)", value=st.session_state.card_data["weight"], key="input_weight")
        
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("✅ تأكيد وحفظ التوب في المخزن والإكسل"):
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
            st.success(f"🎉 تم حفظ التوب بنجاح! كود التوب: ({roll_id})")
        except Exception as e:
            st.error(f"⚠️ خطأ أثناء الإضافة: {e}")

# --- 2️⃣ صرف توب ---
elif menu == "➖ صرف توب (Stock-Out)":
    st.subheader("📤 صرف وتخصيم توب")
    stock_df = pd.read_sql_query("SELECT roll_id, supplier_name, fabric_name, color_shade, metres FROM inventory WHERE status='IN_STOCK'", conn)
    
    if stock_df.empty:
        st.info("لا توجد أتواب متاحة بالمخزن حالياً للصرف.")
    else:
        selected_roll = st.selectbox("اختر كود التوب المراد صرفه:", stock_df['roll_id'].tolist())
        roll_details = stock_df[stock_df['roll_id'] == selected_roll].iloc[0]
        st.warning(f"تفاصيل: {roll_details['fabric_name']} | لون {roll_details['color_shade']} | {roll_details['metres']} متر")
        
        if st.button("🗑️ تأكيد الصرف"):
            cursor = conn.cursor()
            cursor.execute("UPDATE inventory SET status='DISPATCHED' WHERE roll_id=?", (selected_roll,))
            conn.commit()
            st.success(f"تم صرف التوب {selected_roll} بنجاح!")

# --- 3️⃣ إدارة الموردين ---
elif menu == "🏢 إضافة/إدارة الموردين":
    st.subheader("🏢 إضافة مورد جديد")
    with st.form("add_supplier"):
        sup_name = st.text_input("اسم المورد", placeholder="اسم المورد")
        sup_desc = st.text_area("ملاحظات / كود الكارت", placeholder="اختياري")
        save_sup = st.form_submit_button("حفظ المورد")
        if save_sup and sup_name:
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO suppliers (supplier_name, description) VALUES (?, ?)", (sup_name, sup_desc))
                conn.commit()
                st.success(f"تم تسجيل المورد '{sup_name}'!")
            except:
                st.error("المورد مسجل مسبقاً!")
                
    st.dataframe(pd.read_sql_query("SELECT supplier_name AS 'اسم المورد', description AS 'الملاحظات' FROM suppliers", conn), use_container_width=True)

# --- 4️⃣ شيت المخزون وتصدير الإكسل ---
elif menu == "📊 شيت المخزون والإكسل":
    st.subheader("📊 المخزون وتصدير ملف الإكسل")
    
    excel_data = export_inventory_to_excel_with_images()
    st.download_button(
        label="📥 تحميل شيت الإكسل الكامل (مدمج بالصور) Excel",
        data=excel_data,
        file_name=f"Warehouse_Inventory_With_Pictures_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.markdown("---")
    df = pd.read_sql_query("SELECT roll_id AS 'كود التوب', supplier_name AS 'المورد', fabric_name AS 'الخامة', color_shade AS 'اللون', pc_no AS 'رقم التوب', lot_no AS 'اللوت', metres AS 'متر', weight_kg AS 'كجم', status AS 'الحالة' FROM inventory", conn)
    st.dataframe(df, use_container_width=True)

conn.close()
