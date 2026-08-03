import sqlite3
import pandas as pd
import streamlit as st

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

# ----------------- 2. إعدادات الواجهة الخاصة بالموبايل -----------------
st.set_page_config(
    page_title="نظام تتبع الأقمشة",
    page_icon="🧵",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# تنسيق عريض ومناسب للموبايل
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3.2em;
        font-weight: bold;
        font-size: 16px;
    }
    div[data-baseweb="select"] {
        border-radius: 10px;
    }
    .main-title {
        text-align: center;
        color: #1E88E5;
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🧵 إدارة مخزن الأقمشة</div>', unsafe_allow_html=True)

menu = st.sidebar.radio("القائمة الرئيسية", [
    "📸 إضافة توب للمخزن (Stock-In)", 
    "➖ صرف توب (Stock-Out)", 
    "🏢 إضافة/إدارة الموردين", 
    "📊 شيت المخزون الحالي"
])

conn = sqlite3.connect('warehouse_system.db')

# --- 1️⃣ إضافة توب جديد ---
if menu == "📸 إضافة توب للمخزن (Stock-In)":
    st.subheader("📥 إدخال توب جديد")
    
    suppliers_df = pd.read_sql_query("SELECT supplier_name FROM suppliers", conn)
    supplier_list = suppliers_df['supplier_name'].tolist() if not suppliers_df.empty else ['El-basha']
    selected_supplier = st.selectbox("🏷️ اختر المورد:", supplier_list)
    
    st.markdown("---")
    
    # اختيار طريقة تصوير/رفع الصورة
    source_type = st.radio(
        "اختر طريقة تصوير كارت التوب:",
        ["📸 التقاط صورة مباشرة (الكاميرا)", "📁 اختيار صورة من المعرض (Gallery)"],
        horizontal=False
    )
    
    img_file = None
    
    if "📸 التقاط صورة" in source_type:
        # أداة الكاميرا المباشرة مع زر التقاط صريح
        img_file = st.camera_input("اضغط الزر بالأسفل لالتقاط صورة الكارت")
    else:
        # اختيار صورة من الاستوديو
        img_file = st.file_uploader("اختر صورة الكارت من المعرض", type=["jpg", "png", "jpeg", "webp"])

    # معاينة الصورة عند التقاطها أو اختيارها
    if img_file is not None:
        st.image(img_file, caption="معاينة كارت التوب الملتقط", use_column_width=True)
        st.success("✅ تم التقط/رفع الصورة بنجاح! راجع البيانات بالأسفل وأكد الحفظ.")

    st.markdown("### 📝 بيانات التوب")
    
    # نموذج البيانات - جميع الخانات فارغة بشكل افتراضي
    with st.form("add_roll_form", clear_on_submit=True):
        fabric_name = st.text_input("اسم الخامة (Fabric)", value="", placeholder="مثال: Rosetta")
        color_shade = st.text_input("اللون / الدرجة (Shade)", value="", placeholder="مثال: Scour")
        
        c1, c2 = st.columns(2)
        with c1:
            pc_no_input = st.text_input("رقم التوب (PC NO.)", value="", placeholder="مثال: 38")
            metres_input = st.text_input("الأمتار (Metres)", value="", placeholder="مثال: 118.5")
        with c2:
            lot_no_input = st.text_input("رقم اللوت (LOT NO.)", value="", placeholder="مثال: 5")
            weight_input = st.text_input("الوزن (Kgs)", value="", placeholder="مثال: 23.8")
            
        st.markdown("<br>", unsafe_allow_html=True)
        submit_btn = st.form_submit_button("✅ تأكيد وحفظ التوب في المخزن")
        
        if submit_btn:
            # التحقق من أن الخانات الأساسية تم ملؤها
            if not fabric_name or not pc_no_input or not lot_no_input:
                st.error("⚠️ يرجى ملء اسم الخامة ورقم التوب ورقم اللوت على الأقل قبل الحفظ!")
            else:
                try:
                    pc_no = int(pc_no_input)
                    lot_no = int(lot_no_input)
                    metres = float(metres_input) if metres_input else 0.0
                    weight_kg = float(weight_input) if weight_input else 0.0
                    
                    roll_id = f"ROLL-{selected_supplier[:3].upper()}-{pc_no}-L{lot_no}"
                    
                    cursor = conn.cursor()
                    cursor.execute('''
                    INSERT INTO inventory (roll_id, supplier_name, fabric_name, color_shade, pc_no, lot_no, metres, weight_kg, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'IN_STOCK')
                    ''', (roll_id, selected_supplier, fabric_name, color_shade, pc_no, lot_no, metres, weight_kg))
                    conn.commit()
                    st.balloons()
                    st.success(f"🎉 تم حفظ التوب كود ({roll_id}) بنجاح في المخزن!")
                except ValueError:
                    st.error("⚠️ يرجى التأكد من كتابة الأرقام بشكل صحيح في خانات (رقم التوب، اللوت، الأمتار، والوزن).")
                except Exception as e:
                    st.error("⚠️ هذا التوب مسجل في المخزن مسبقاً بنفس الأرقام!")

# --- 2️⃣ صرف توب ---
elif menu == "➖ صرف توب (Stock-Out)":
    st.subheader("📤 صرف وتخصيم توب")
    stock_df = pd.read_sql_query("SELECT roll_id, supplier_name, fabric_name, color_shade, metres FROM inventory WHERE status='IN_STOCK'", conn)
    
    if stock_df.empty:
        st.info("لا توجد أتواب متاحة بالمخزن حالياً للصرف.")
    else:
        selected_roll = st.selectbox("اختر كود التوب المراد صرفه:", stock_df['roll_id'].tolist())
        roll_details = stock_df[stock_df['roll_id'] == selected_roll].iloc[0]
        
        st.warning(f"تفاصيل: خامة {roll_details['fabric_name']} | لون {roll_details['color_shade']} | {roll_details['metres']} متر")
        
        if st.button("🗑️ تأكيد الصرف والتخصيم"):
            cursor = conn.cursor()
            cursor.execute("UPDATE inventory SET status='DISPATCHED' WHERE roll_id=?", (selected_roll,))
            conn.commit()
            st.success(f"تم صرف التوب {selected_roll} بنجاح!")

# --- 3️⃣ إدارة الموردين ---
elif menu == "🏢 إضافة/إدارة الموردين":
    st.subheader("🏢 إضافة مورد جديد")
    with st.form("add_supplier"):
        sup_name = st.text_input("اسم المورد", placeholder="مثال: الباشا")
        sup_desc = st.text_area("ملاحظات / كود نموذج الكارت", placeholder="اختياري")
        save_sup = st.form_submit_button("حفظ المورد")
        if save_sup and sup_name:
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO suppliers (supplier_name, description) VALUES (?, ?)", (sup_name, sup_desc))
                conn.commit()
                st.success(f"تم تسجيل المورد '{sup_name}'!")
            except:
                st.error("المورد مسجل مسبقاً!")
                
    st.markdown("### قائمة الموردين المسجلين:")
    st.dataframe(pd.read_sql_query("SELECT supplier_name AS 'اسم المورد', description AS 'الملاحظات' FROM suppliers", conn), use_container_width=True)

# --- 4️⃣ شيت المخزون ---
elif menu == "📊 شيت المخزون الحالي":
    st.subheader("📊 جدول المخزون الحالي")
    df = pd.read_sql_query("SELECT roll_id AS 'كود التوب', supplier_name AS 'المورد', fabric_name AS 'الخامة', color_shade AS 'اللون', pc_no AS 'رقم التوب', lot_no AS 'اللوت', metres AS 'متر', weight_kg AS 'كجم', status AS 'الحالة' FROM inventory", conn)
    st.dataframe(df, use_container_width=True)

conn.close()
