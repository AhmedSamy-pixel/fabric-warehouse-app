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

st.set_page_config(page_title="نظام مخازن الأقمشة", layout="wide")
st.title("🧵 نظام تتبع الأقمشة - الكاميرا الخلفية حصراً")

menu = st.sidebar.radio("القائمة الرئيسية", ["📸 إضافة توب للمخزن (Stock-In)", "➖ صرف توب (Stock-Out)", "🏢 إضافة/إدارة الموردين", "📊 شيت المخزون الحالي"])
conn = sqlite3.connect('warehouse_system.db')

if menu == "📸 إضافة توب للمخزن (Stock-In)":
    st.header("إضافة توب جديد عبر الكاميرا الخلفية")
    
    suppliers_df = pd.read_sql_query("SELECT supplier_name FROM suppliers", conn)
    supplier_list = suppliers_df['supplier_name'].tolist() if not suppliers_df.empty else ['El-basha']
    selected_supplier = st.selectbox("اختر المورد:", supplier_list)
    
    st.write("---")
    
    # مكون HTML5 يفرض الكاميرا الخلفية مباشرة (facingMode: environment)
    html_camera_code = """
    <div style="text-align: center;">
        <video id="webcam" autoplay playsinline width="100%" style="max-width: 400px; border: 2px solid #4CAF50; border-radius: 10px;"></video>
        <br><br>
        <button id="snap" style="background-color: #4CAF50; color: white; padding: 12px 24px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer;">
            📸 التقاط صورة الكارت
        </button>
        <br><br>
        <canvas id="canvas" style="display:none;"></canvas>
    </div>

    <script>
        const video = document.getElementById('webcam');
        const canvas = document.getElementById('canvas');
        const snap = document.getElementById('snap');

        // إجبار النظام على استخدام الكاميرا الخلفية فقط (environment)
        const constraints = {
            video: {
                facingMode: { exact: "environment" }
            }
        };

        // في حالة عدم دعم exact يتم التحويل للهاتف بشكل مرن على الكاميرا الخلفية
        navigator.mediaDevices.getUserMedia(constraints)
            .then((stream) => {
                video.srcObject = stream;
            })
            .catch((err) => {
                // محاولة ثانية بدعم عريض للكاميرا الخلفية
                navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
                    .then((stream) => { video.srcObject = stream; })
                    .catch((error) => { alert("تعذر الوصول للكاميرا الخلفية: " + error); });
            });

        snap.addEventListener("click", () => {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext('2d').drawImage(video, 0, 0);
            alert("تم التقاط الصورة من الكاميرا الخلفية بنجاح!");
        });
    </script>
    """
    
    # عرض الكاميرا الخلفية المباشرة
    components.html(html_camera_code, height=420)
    
    st.success("راجع بيانات التوب واضغط تأكيد الإضافة:")
    
    # نموذج البيانات وزر التأكيد
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
            
        submit_btn = st.form_submit_button("✅ تأكيد وإضافة التوب للمخزن")
        
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
                st.error("هذا التوب مسجل في المخزن بالفعل!")

elif menu == "➖ صرف توب (Stock-Out)":
    st.header("صرف وتخصيم توب من المخزن")
    stock_df = pd.read_sql_query("SELECT roll_id, supplier_name, fabric_name, color_shade, metres FROM inventory WHERE status='IN_STOCK'", conn)
    if stock_df.empty:
        st.info("لا توجد أتواب متاحة بالمخزن حالياً للصرف.")
    else:
        selected_roll = st.selectbox("اختر كود التوب المراد صرفه:", stock_df['roll_id'].tolist())
        if st.button("🗑️ تأكيد الصرف والتخصيم من المخزن"):
            cursor = conn.cursor()
            cursor.execute("UPDATE inventory SET status='DISPATCHED' WHERE roll_id=?", (selected_roll,))
            conn.commit()
            st.success(f"تم صرف التوب {selected_roll} وتخصيمه من المخزن!")

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
    st.dataframe(pd.read_sql_query("SELECT * FROM suppliers", conn))

elif menu == "📊 شيت المخزون الحالي":
    st.header("شيت المخزن اللحظي")
    st.dataframe(pd.read_sql_query("SELECT * FROM inventory", conn))

conn.close()
