import os
import io
import sqlite3
import re
import pandas as pd
import numpy as np
import streamlit as st
from PIL import Image
import easyocr
import openpyxl
from openpyxl.drawing.image import Image as OpenpyxlImage

# ----------------- 1. تهيئة قاعدة البيانات والتطبيقات -----------------
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
        pc_no INTEGER,
        lot_no INTEGER,
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

# إنشاء مجلد حفظ صور الأتواب
if not os.path.exists('roll_images'):
    os.makedirs('roll_images')

# تحميل قارئ النصوص (OCR)
@st.cache_resource
def load_ocr_reader():
    return easyocr.Reader(['en'], gpu=False)

reader = load_ocr_reader()

# دالة استخراج البيانات من صورة كارت التوب
def parse_card_image(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))
    img_np = np.array(image)
    
    # قراءة جميع النصوص من الصورة
    results = reader.readtext(img_np, detail=0)
    full_text = " ".join(results)
    
    extracted = {
        "fabric": "",
        "shade": "",
        "pc_no": "",
        "lot_no": "",
        "metres": "",
        "weight": ""
    }
    
    # البحث عن الأرقام والأنماط من خلال القواعد الذكية
    pc_match = re.search(r'(?:PC|P/C|NO|P\.C)[^\d]*(\d+)', full_text, re.IGNORECASE)
    if pc_match:
        extracted["pc_no"] = pc_match.group(1)
        
    lot_match = re.search(r'(?:LOT|L/O)[^\d]*(\d+)', full_text, re.IGNORECASE)
    if lot_match:
        extracted["lot_no"] = lot_match.group(1)

    metres_match = re.search(r'(?:METRES|MTR|MTRS|METER)[^\d]*(\d+(?:\.\d+)?)', full_text, re.IGNORECASE)
    if metres_match:
        extracted["metres"] = metres_match.group(1)

    weight_match = re.search(r'(?:KGS|KG|WEIGHT)[^\d]*(\d+(?:\.\d+)?)', full_text, re.IGNORECASE)
    if weight_match:
        extracted["weight"] = weight_match.group(1)

    # محاولة استخراج كلمات الخامات الشائعة
    fabrics_list = ["Rosetta", "Milton", "Cotton", "Polyester", "Lycra", "Single Jersey", "Interlock"]
    for fab in fabrics_list:
        if fab.lower() in full_text.lower():
            extracted["fabric"] = fab
            break
            
    # محاولة استخراج ألوان شائعة
    shades_list = ["Scour", "White", "Black", "Navy", "Red", "Blue", "Grey", "Beige"]
    for sh in shades_list:
        if sh.lower() in full_text.lower():
            extracted["shade"] = sh
            break

    return extracted, full_text

# دالة إنشاء وتصدير شيت إكسل يتضمن الصور
def export_inventory_to_excel_with_images():
    conn = sqlite3.connect('warehouse_system.db')
    df = pd.read_sql_query("SELECT roll_id, supplier_name, fabric_name, color_shade, pc_no, lot_no, metres, weight_kg, image_path, status, date_added FROM inventory", conn)
    conn.close()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "المخزون الحالي"
    
    # كتابة الهيدر
    headers = ["كود التوب", "المورد", "اسم الخامة", "اللون / الدرجة", "رقم التوب", "اللوت", "الأمتار", "الوزن (كجم)", "Ref# Picture", "الحالة", "تاريخ الإضافة"]
    ws.append(headers)
    
    # تنسيق الصف الأول (الهيدر)
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = openpyxl.styles.Font(bold=True, color="FFFFFF")
        cell.fill = openpyxl.styles.PatternFill(start_color="1E88E5", end_color="1E88E5", fill_type="solid")
        cell.alignment = openpyxl.styles.Alignment(horizontal="center", vertical="center")
        
    ws.row_dimensions[1].height = 25
    
    # كتابة البيانات وإضافة الصور
    for idx, row in df.iterrows():
        row_num = idx + 2
        ws.row_dimensions[row_num].height = 65 # ارتفاع كافٍ للصورة
        
        ws.cell(row=row_num, column=1, value=row['roll_id'])
        ws.cell(row=row_num, column=2, value=row['supplier_name'])
        ws.cell(row=row_num, column=3, value=row['fabric_name'])
        ws.cell(row=row_num, column=4, value=row['color_shade'])
        ws.cell(row=row_num, column=5, value=row['pc_no'])
        ws.cell(row=row_num, column=6, value=row['lot_no'])
        ws.cell(row=row_num, column=7, value=row['metres'])
        ws.cell(row=row_num, column=8, value=row['weight_kg'])
        ws.cell(row=row_num, column=10, value=row['status'])
        ws.cell(row=row_num, column=11, value=str(row['date_added']))
        
        # إضافة الصورة في خلية Ref# Picture (العمود 9)
        img_path = row['image_path']
        if img_path and os.path.exists(img_path):
            try:
                img = Image.open(img_path)
                img.thumbnail((80, 80)) # تصغير حجم الصورة للخلية
                
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                
                xl_img = OpenpyxlImage(img_byte_arr)
                xl_img.width = 75
                xl_img.height = 75
                
                cell_address = f"I{row_num}"
                ws.add_image(xl_img, cell_address)
            except Exception as e:
                ws.cell(row=row_num, column=9, value="خطأ في الصورة")
        else:
            ws.cell(row=row_num, column=9, value="لا توجد صورة")

    # تعديل عرض الأعمدة
    for col in ws.columns:
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        if col_letter == 'I':
            ws.column_dimensions[col_letter].width = 16 # عرض عمود الصورة
        else:
            ws.column_dimensions[col_letter].width = 18

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

# ----------------- 2. إعدادات واجهة الموبايل -----------------
st.set_page_config(page_title="نظام تتبع الأقمشة", page_icon="🧵", layout="centered")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 12px; height: 3.2em; font-weight: bold; font-size: 16px; }
    .main-title { text-align: center; color: #1E88E5; font-size: 24px; font-weight: bold; margin-bottom: 20px; }
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
    st.subheader("📥 إدخال توب جديد")
    
    suppliers_df = pd.read_sql_query("SELECT supplier_name FROM suppliers", conn)
    supplier_list = suppliers_df['supplier_name'].tolist() if not suppliers_df.empty else ['El-basha']
    selected_supplier = st.selectbox("🏷️ اختر المورد:", supplier_list)
    
    st.markdown("---")
    
    source_type = st.radio("اختر طريقة التصوير:", ["📸 التقاط صورة مباشرة", "📁 اختيار صورة من المعرض"], horizontal=True)
    
    img_file = None
    if "📸 التقاط صورة" in source_type:
        img_file = st.camera_input("اضغط لالتقاط صورة الكارت")
    else:
        img_file = st.file_uploader("اختر صورة الكارت", type=["jpg", "png", "jpeg", "webp"])

    # تهيئة قيم الاستخراج
    parsed_data = {"fabric": "", "shade": "", "pc_no": "", "lot_no": "", "metres": "", "weight": ""}
    img_saved_path = ""

    if img_file is not None:
        image_bytes = img_file.getvalue()
        st.image(image_bytes, caption="معاينة كارت التوب الملتقط", use_column_width=True)
        
        with st.spinner("🔍 جاري قراءة واستخراج البيانات من الكارت تلقائياً..."):
            parsed_data, raw_ocr = parse_card_image(image_bytes)
            st.success("✅ تم قراءة البيانات تلقائياً من الصورة! راجعها وقم بتعديلها إن لزم:")
            
        # حفظ الصورة مؤقتاً لشيت الإكسل
        temp_img_name = f"roll_{selected_supplier}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.png"
        img_saved_path = os.path.join('roll_images', temp_img_name)
        with open(img_saved_path, 'wb') as f:
            f.write(image_bytes)

    st.markdown("### 📝 بيانات التوب المستخرجة")
    
    # ملء الخانات بالبيانات المتم قراءتها
    with st.form("add_roll_form", clear_on_submit=True):
        fabric_name = st.text_input("اسم الخامة (Fabric)", value=parsed_data["fabric"], placeholder="أدخل اسم الخامة")
        color_shade = st.text_input("اللون / الدرجة (Shade)", value=parsed_data["shade"], placeholder="أدخل اللون")
        
        c1, c2 = st.columns(2)
        with c1:
            pc_no_input = st.text_input("رقم التوب (PC NO.)", value=parsed_data["pc_no"], placeholder="رقم التوب")
            metres_input = st.text_input("الأمتار (Metres)", value=parsed_data["metres"], placeholder="الأمتار")
        with c2:
            lot_no_input = st.text_input("رقم اللوت (LOT NO.)", value=parsed_data["lot_no"], placeholder="رقم اللوت")
            weight_input = st.text_input("الوزن (Kgs)", value=parsed_data["weight"], placeholder="الوزن")
            
        submit_btn = st.form_submit_button("✅ تأكيد وحفظ التوب في المخزن والإكسل")
        
        if submit_btn:
            if not fabric_name or not pc_no_input or not lot_no_input:
                st.error("⚠️ يرجى إدخال اسم الخامة ورقم التوب واللوت على الأقل!")
            else:
                try:
                    pc_no = int(pc_no_input)
                    lot_no = int(lot_no_input)
                    metres = float(metres_input) if metres_input else 0.0
                    weight_kg = float(weight_input) if weight_input else 0.0
                    
                    roll_id = f"ROLL-{selected_supplier[:3].upper()}-{pc_no}-L{lot_no}"
                    
                    cursor = conn.cursor()
                    cursor.execute('''
                    INSERT INTO inventory (roll_id, supplier_name, fabric_name, color_shade, pc_no, lot_no, metres, weight_kg, image_path, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'IN_STOCK')
                    ''', (roll_id, selected_supplier, fabric_name, color_shade, pc_no, lot_no, metres, weight_kg, img_saved_path))
                    conn.commit()
                    st.balloons()
                    st.success(f"🎉 تم حفظ التوب كود ({roll_id}) والصورة بنجاح!")
                except ValueError:
                    st.error("⚠️ يرجى كتابة أرقام صحيحة في خانات (التوب، اللوت، المتر، والوزن).")
                except Exception as e:
                    st.error("⚠️ هذا التوب مسجل مسبقاً بنفس الرقم واللوت!")

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
    
    # زر تحميل الإكسل المدمج بالصور
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
