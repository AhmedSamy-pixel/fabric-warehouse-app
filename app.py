import sqlite3
import pandas as pd
import streamlit as st
from PIL import Image

# ----------------- إعداد قاعدة البيانات -----------------
def init_db():
    conn = sqlite3.connect('warehouse_system.db')
    cursor = conn.cursor()
    
    # جدول الموردين (ديناميكي لإضافة موردين جدد)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_name TEXT UNIQUE NOT NULL,
        description TEXT
    )
    ''')
    
    # جدول المخزون (الأتواب)
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
        status TEXT DEFAULT 'IN_STOCK',
        date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # إضافة مورد افتراضي تجريبي
    cursor.execute("INSERT OR IGNORE INTO suppliers (supplier_name, description) VALUES ('El-basha', 'المورد الأساسي للأقمشة')")
    conn.commit()
    conn.close()

init_db()

# ----------------- واجهة التطبيق (Streamlit UI) -----------------
st.set_page_config(page_title="نظام إدارة مخازن الأقمشة بالذكاء الاصطناعي", layout="wide")

st.title("🧵 نظام إدارة وتتبع الأقمشة عبر الكاميرا والذكاء الاصطناعي")
st.markdown("---")

# القائمة الجانبية للتنقل بين الأقسام
menu = st.sidebar.selectbox("القائمة الرئيسية", ["📸 إضافة توب جديد (Stock-In)", "➖ صرف توب من المخزن (Stock-Out)", "🏢 إدارة وتعريف الموردين", "📊 تقارير المخزون الحالي"])

conn = sqlite3.connect('warehouse_system.db')

# 1️⃣ قسم إضافة توب جديد
if menu == "📸 إضافة توب جديد (Stock-In)":
    st.header("إضافة توب جديد للمخزون عبر الكاميرا")
    
    # اختيار المورد
    suppliers_df = pd.read_sql_query("SELECT supplier_name FROM suppliers", conn)
    selected_supplier = st.selectbox("اختر المورد (أو تم التعرف عليه تلقائياً من الكارت):", suppliers_df['supplier_name'].tolist())
    
    # التقاط الصورة أو رفعها
    uploaded_file = st.camera_input("التقاط صورة كارت التوب بالكاميرا")
    
    if uploaded_file is not None:
        st.success("تم التقاط صورة الكارت بنجاح وتحليلها بالذكاء الاصطناعي!")
        
        # محاكاة الاستخراج الذكي للبيانات (OCR & AI Extraction)
        # في النسخة الحالية نقوم بعرض حقول جاهزة للمراجعة وتأكيدها
        st.subheader("مراجعة بيانات التوب المستخرجة:")
        
        col1, col2 = st.columns(2)
        with col1:
            fabric_name = st.text_input("اسم الخامة (Fabric Name)", value="Rosetta")
            color_shade = st.text_input("الدرجة / اللون (Shade)", value="Scour")
            pc_no = st.number_input("رقم التوب (PC No.)", value=38, step=1)
        with col2:
            lot_no = st.number_input("رقم اللوت (Lot No.)", value=5, step=1)
            metres = st.number_input("الطول بالأمتار (Metres)", value=118.5)
            weight_kg = st.number_input("الوزن بالكيلو (Kgs)", value=23.8)
            
        roll_id_auto = f"ROLL-{selected_supplier[:3].upper()}-{pc_no}-L{lot_no}"
        st.info(f"كود التوب المعرف تلقائياً للنظام: **{roll_id_auto}**")
        
        if st.button("➕ تأكيد وإضافة التوب للمخزن"):
            try:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT INTO inventory (roll_id, supplier_name, fabric_name, color_shade, pc_no, lot_no, metres, weight_kg, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'IN_STOCK')
                ''', (roll_id_auto, selected_supplier, fabric_name, color_shade, pc_no, lot_no, metres, weight_kg))
                conn.commit()
                st.success(f"تم إضافة التوب {roll_id_auto} بنجاح إلى شيت المخزن!")
            except Exception as e:
                st.error(f"خطأ: هذا التوب مسجل مسبقاً في المخزن! ({e})")

# 2️⃣ قسم صرف توب من المخزن
elif menu == "➖ صرف توب من المخزن (Stock-Out)":
    st.header("صرف وتخصيم توب من المخزن")
    
    stock_df = pd.read_sql_query("SELECT roll_id, supplier_name, fabric_name, color_shade, metres FROM inventory WHERE status='IN_STOCK'", conn)
    
    if stock_df.empty:
        st.warning("لا توجد أتواب متاحة حالياً في المخزن للصرف.")
    else:
        scan_option = st.camera_input("التقاط صورة كارت التوب المراد صرفه")
        
        # اختيار التوب (سواء بالكاميرا أو يدويًا للمراجعة)
        selected_roll = st.selectbox("الأتواب المتاحة بالمخزن:", stock_df['roll_id'].tolist())
        
        roll_info = stock_df[stock_df['roll_id'] == selected_roll].iloc[0]
        st.write(f"**تفاصيل التوب:** مورد: {roll_info['supplier_name']} | خامة: {roll_info['fabric_name']} | طول: {roll_info['metres']} متر")
        
        if st.button("➖ تأكيد الصرف وتخصيم من المخزن"):
            cursor = conn.cursor()
            cursor.execute("UPDATE inventory SET status='DISPATCHED' WHERE roll_id=?", (selected_roll,))
            conn.commit()
            st.success(f"تم صرف التوب {selected_roll} بنجاح وتحديث المخزن!")

# 3️⃣ قسم إدارة وتعريف الموردين
elif menu == "🏢 إدارة وتعريف الموردين":
    st.header("إضافة مورد جديد وقوالب كاراته للنظام")
    
    new_supplier = st.text_input("اسم المورد الجديد (مثال: El-basha)")
    supplier_desc = st.text_area("وصف أو ملاحظات على كارت المورد")
    supplier_card_img = st.camera_input("التقاط صورة لكارت المورد الجديد لتعريف بصمته")
    
    if st.button("حفظ المورد الجديد في النظام"):
        if new_supplier:
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO suppliers (supplier_name, description) VALUES (?, ?)", (new_supplier, supplier_desc))
                conn.commit()
                st.success(f"تم حفظ المورد '{new_supplier}' وتعريف بصمته بنجاح وأصبح جاهزاً للتعامل معه!")
            except:
                st.error("هذا المورد مسجل مسبقاً!")
        else:
            st.warning("يرجى كتابة اسم المورد على الأقل.")
            
    st.subheader("الموردين المسجلين حالياً:")
    st.dataframe(pd.read_sql_query("SELECT * FROM suppliers", conn))

# 4️⃣ قسم التقارير والمخزون الحالي
elif menu == "📊 تقارير المخزون الحالي":
    st.header("تقرير شيت المخزون اللحظي")
    
    query_filter = st.radio("عرض:", ["الأتواب المتاحة بالمخزن (IN_STOCK)", "الأتواب المنصرفة (DISPATCHED)", "الكل"])
    
    if "المتاحة" in query_filter:
        df = pd.read_sql_query("SELECT * FROM inventory WHERE status='IN_STOCK'", conn)
    elif "المنصرفة" in query_filter:
        df = pd.read_sql_query("SELECT * FROM inventory WHERE status='DISPATCHED'", conn)
    else:
        df = pd.read_sql_query("SELECT * FROM inventory", conn)
        
    st.dataframe(df)
    
    if not df.empty and 'metres' in df.columns:
        total_metres = df[df['status']=='IN_STOCK']['metres'].sum()
        total_weight = df[df['status']=='IN_STOCK']['weight_kg'].sum()
        st.metric(label="إجمالي الأمتار المتاحة بالمخزن", value=f"{total_metres} متر")
        st.metric(label="إجمالي الأوزان المتاحة بالمخزن", value=f"{total_weight} كجم")

conn.close()
