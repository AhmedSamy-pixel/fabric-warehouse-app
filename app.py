import sqlite3
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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
    layout="centered", # مخصص للعرض الرأسي على شاشات الموبايل
    initial_sidebar_state="collapsed"
)

# تصميم وتنسيق مخصص CSS للموبايل
st.markdown("""
    <style>
    /* تحسين العرض على الموبايل */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3em;
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
    .card-box {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        margin-bottom: 15px;
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
    
    # اختيار طريقة التقاط/رفع الصورة
    source_type = st.radio(
        "اختر طريقة إدخال صورة كارت التوب:",
        ["📁 اختيار من المعرض (Gallery)", "📸 فتح الكاميرا الخلفية مباشرة"],
        horizontal=False
    )
    
    img_file = None
    
    if "📁 اختيار من المعرض" in source_type:
        img_file = st.file_uploader("اختر صورة من الجليري / الاستوديو", type=["jpg", "png", "jpeg", "webp"])
    else:
        # الكاميرا الخلفية إجبارياً عبر HTML5
        html_camera_code = """
        <div style="text-align: center; width: 100%;">
            <video id="webcam" autoplay playsinline style="width: 100%; max-width: 350px; border: 2px solid #1E88E5; border-radius: 12px;"></video>
            <br><br>
            <button id="snap" style="background-color: #1E88E5; color: white; padding: 12px; width: 100%; border: none; border-radius: 10px; font-weight: bold; font-size: 16px;">
                📸 التقاط صورة الكارت الآن
            </button>
            <canvas id="canvas" style="display:none;"></canvas>
        </div>

        <script>
            const video = document.getElementById('webcam');
            const canvas = document.getElementById('canvas');
            const snap = document.getElementById('snap');

            navigator.mediaDevices.getUserMedia({ video: { facingMode: { exact: "environment" } } })
                .then((stream) => { video.srcObject = stream; })
                .catch((err) => {
                    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
                        .then((stream) => { video.srcObject = stream; })
                        .catch((error) => { console.log("Camera error: " + error); });
                });

            snap.addEventListener("click", () => {
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                canvas.getContext('2d').drawImage(video, 0, 0);
                alert("تم التقط الصورة من الكاميرا الخلفية بنجاح!");
            });
        </script>
        """
        components.html(html_camera_code, height=380)

    # عرض المعاينة ورسالة نجاح التقاط الصورة
    if img_file is not None:
        st.image(img_file, caption="معاينة كارت التوب الملتقط", use_column_width=True)
        st.success("✅ تم اختيار الصورة بنجاح! راجع البيانات وأكد الإضافة.")
    
    st.markdown("### 📝 تفاصيل بيانات التوب")
    
    with st.form("add_roll_form"):
        fabric_name = st.text_input("اسم الخامة (Fabric)", value="Rosetta")
        color_shade = st.text_input("اللون / الدرجة (Shade)", value="Scour")
        
        c1, c2 = st.columns(2)
        with c1:
            pc_no = st.number_input("رقم التوب (PC NO.)", value=38, step=1)
            metres = st.number_input("الأمتار (Metres)", value=118.5)
        with c2:
            lot_no = st.number_input("رقم اللوت (LOT NO.)", value=5, step=1)
            weight_kg = st.number_input("الوزن (Kgs)", value=23.8)
            
        st.markdown("<br>", unsafe_allow_html=True)
        submit_btn = st.form_submit_button("✅ تأكيد وحفظ التوب في المخزن")
        
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
                st.success(f"🎉 تم حفظ التوب كود ({roll_id}) بنجاح!")
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
        sup_name = st.text_input("اسم المورد")
        sup_desc = st.text_area("ملاحظات / كود نموذج الكارت")
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
