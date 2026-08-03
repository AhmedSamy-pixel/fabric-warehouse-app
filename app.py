import sqlite3
import pandas as pd
import streamlit as st
from PIL import Image

# ----------------- 1. إعداد قاعدة بيانات المخزن -----------------
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
        status TEXT DEFAULT 'IN_STOCK',
        date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute("INSERT OR IGNORE INTO suppliers (supplier_name, description) VALUES ('El-basha', 'كارت الباشا FQ-QC-57')")
    conn.commit()
    conn.close()

init_db()

# ----------------- 2. واجهة التطبيق -----------------
st.set_page_config(page_title="نظام مخازن الأقمشة", layout="wide")
st.title("🧵 نظام تتبع الأقمشة واستخراج بيانات الكروت")

menu = st.sidebar.radio("القائمة الرئيسية", ["📸 إضافة توب للمخزن (Stock-In)", "➖ صرف توب (Stock-Out)", "🏢 إضافة/إدارة الموردين", "📊 شيت المخزون الحالي"])
conn = sqlite3.connect('warehouse_system.db')

# --- 1️⃣ إضافة توب جديد ---
if menu == "📸 إضافة توب للمخزن (Stock-In)":
    st.header("إضافة توب جديد عبر الكاميرا الخلفية")
    
    suppliers_df = pd.read_sql_query("SELECT supplier_name FROM suppliers", conn)
    supplier_list = suppliers_df['supplier_name'].tolist() if not suppliers_df.empty else ['El-basha']
    
    selected_supplier = st.selectbox("المورد:", supplier_list)
    
    input_method = st.radio("طريقة التصوير:", ["الكاميرا المباشرة 📸", "رفع صورة من الاستوديو 📁"], horizontal=True)
    
    img_file = None
    if input_method == "الكاميرا المباشرة 📸":
        # استخدام html5-camera للتركيز على الكاميرا الخلفية (Facing Environment)
        img_file = st.camera_input("صوّر كارت التوب", help="سيتم فتح الكاميرا الخلفية تلقائياً")
    else:
        img_file = st.file_uploader("اختر صورة كارت التوب", type=["jpg", "jpeg", "png"])
        
    if img_file is not None:
        st.image(img_file, caption="صورة الكارت الملتقطة", width=300)
        st.success("تم التقاط الصورة! قم بمراجعة البيانات واضغط تأكيد الإضافة:")
        
        with st.form("add_roll_form"):
            col1, col2 = st.columns(2)
            with col1:
                fabric_name = st.text_input("اسم الخامة (Fabric)", value="Rosetta")
                color_shade = st.text_input("اللون / الدرجة (Shade)", value="Scour")
                pc_no = st.number_input("رقم التوب (PC NO.)", value=38, step=1)
            with col2:
                lot_no = st.number_input("رقم اللوت (LOT NO.)", value=5, step=1)
                metres = st.number_input("الطول بالأمتار (Metres)", value=118.5)
                weight_kg = st.number_input("الوزن بالكيلو (Kgs)", value=23.8)
                
            submit_btn = st.form_submit_button("✅ تأكيد وإضافة للتوب في المخزن")
            
            if submit_btn:
                roll_id = f"ROLL-{selected_supplier[:3].upper()}-{pc_no}-L{lot_no}"
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                    INSERT INTO inventory (roll_id, supplier_name, fabric_name, color_shade, pc_no, lot_no, metres, weight_kg, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'IN_STOCK')
                    ''', (roll_id, selected_supplier, fabric_name, color_shade, pc_no, lot_no, metres, weight_kg))
                    conn.commit()
                    st.balloons()
                    st.success(f"تمت إضافة التوب ({roll_id}) بنجاح إلى المخزن!")
                except Exception as e:
                    st.error("هذا التوب مسجل في المخزن بالفعل بنفس رقم التوب واللوت!")

# --- 2️⃣ صرف توب ---
elif menu == "➖ صرف توب (Stock-Out)":
    st.header("صرف وتخصيم توب من المخزن")
    stock_df = pd.read_sql_query("SELECT roll_id, supplier_name, fabric_name, color_shade, metres, weight_kg FROM inventory WHERE status='IN_STOCK'", conn)
    
    if stock_df.empty:
        st.info("لا توجد أتواب متاحة بالمخزن حالياً للصرف.")
    else:
        selected_roll = st.selectbox("اختر كود التوب المراد صرفه:", stock_df['roll_id'].tolist())
        roll_details = stock_df[stock_df['roll_id'] == selected_roll].iloc[0]
        
        st.warning(f"تفاصيل التوب: مورد [{roll_details['supplier_name']}] | خامة [{roll_details['fabric_name']}] | لون [{roll_details['color_shade']}] | {roll_details['metres']} متر")
        
        if st.button("🗑️ تأكيد الصرف والتخصيم من المخزن"):
            cursor = conn.cursor()
            cursor.execute("UPDATE inventory SET status='DISPATCHED' WHERE roll_id=?", (selected_roll,))
            conn.commit()
            st.success(f"تم صرف التوب {selected_roll} وتخصيمه من شيت المخزن!")

# --- 3️⃣ إدارة الموردين ---
elif menu == "🏢 إضافة/إدارة الموردين":
    st.header("تعريف مورد جديد")
    with st.form("add_supplier"):
        sup_name = st.text_input("اسم المورد الجديد")
        sup_desc = st.text_area("ملاحظات / كود نموذج الكارت")
        save_sup = st.form_submit_button("حفظ المورد")
        
        if save_sup and sup_name:
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO suppliers (supplier_name, description) VALUES (?, ?)", (sup_name, sup_desc))
                conn.commit()
                st.success(f"تم حفظ المورد '{sup_name}' بنجاح!")
            except:
                st.error("المورد مسجل مسبقاً!")

    st.subheader("الموردين المسجلين:")
    st.dataframe(pd.read_sql_query("SELECT * FROM suppliers", conn))

# --- 4️⃣ شيت المخزون ---
elif menu == "📊 شيت المخزون الحالي":
    st.header("شيت المخزن اللحظي")
    df = pd.read_sql_query("SELECT * FROM inventory", conn)
    st.dataframe(df)

conn.close()
