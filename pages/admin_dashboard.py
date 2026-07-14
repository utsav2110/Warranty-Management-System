import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from app import get_conn, Image, io, FPDF, MIMEMultipart, MIMEText, MIMEApplication, smtplib,os,get_user_email

def get_user_stats():
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COUNT(*) FROM users 
        WHERE created_at >= NOW() - INTERVAL '7 days'
    """)
    new_users = cur.fetchone()[0]
    
    cur.execute("""
        SELECT role, COUNT(*) FROM users 
        GROUP BY role
    """)
    roles = cur.fetchall()
    
    cur.close()
    conn.close()
    return total_users, new_users, roles

def get_warranty_stats():
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM warranty_items")
    total_warranties = cur.fetchone()[0]
    
    cur.execute("""
        SELECT category, COUNT(*) FROM warranty_items 
        GROUP BY category
    """)
    categories = cur.fetchall()
    
    cur.execute("""
        SELECT COUNT(*) FROM warranty_items 
        WHERE warranty_end_date <= NOW() + INTERVAL '7 days'
    """)
    expiring_soon = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    return total_warranties, categories, expiring_soon

def get_user_item_stats():
    conn = get_conn()
    cur = conn.cursor()
    
    # Top users by item count
    cur.execute("""
        SELECT u.username, COUNT(w.id) as item_count
        FROM users u
        LEFT JOIN warranty_items w ON u.user_id = w.user_id
        WHERE u.role = 'user'
        GROUP BY u.username
        ORDER BY item_count DESC
        LIMIT 10
    """)
    top_users = cur.fetchall()
    
    # Category leaders
    cur.execute("""
        WITH CategoryLeaders AS (
            SELECT 
                u.username,
                w.category,
                COUNT(*) as category_count,
                ROW_NUMBER() OVER (PARTITION BY w.category ORDER BY COUNT(*) DESC) as rn
            FROM warranty_items w
            JOIN users u ON w.user_id = u.user_id
            GROUP BY u.username, w.category
        )
        SELECT username, category, category_count
        FROM CategoryLeaders
        WHERE rn = 1
        ORDER BY category_count DESC
    """)
    category_leaders = cur.fetchall()
    
    cur.close()
    conn.close()
    return top_users, category_leaders

if not st.session_state.get("logged_in") or st.session_state.get("role") != "admin":
    st.error("Access Denied. Admin rights required.")
    st.stop()

def generate_admin_users_pdf():
    pdf = FPDF()
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT u.user_id, u.username, u.email, u.role, u.created_at,
               COUNT(w.id) as total_warranties
        FROM users u
        LEFT JOIN warranty_items w ON u.user_id = w.user_id
        GROUP BY u.user_id, u.username, u.email, u.role, u.created_at
        ORDER BY u.created_at DESC
    """)
    users = cur.fetchall()
    
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Users Report', ln=True, align='C')
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)
    
    for user in users:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, f'User: {user[1]}', ln=True)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 8, f'ID: {user[0]}', ln=True)
        pdf.cell(0, 8, f'Email: {user[2]}', ln=True)
        pdf.cell(0, 8, f'Role: {user[3]}', ln=True)
        pdf.cell(0, 8, f'Created: {user[4]}', ln=True)
        pdf.cell(0, 8, f'Total Warranties: {user[5]}', ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(10)
    
    cur.close()
    conn.close()
    return pdf.output(dest='S').encode('latin-1')

def generate_admin_warranties_pdf():
    pdf = FPDF()
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT w.id, u.username, u.email, w.item_name, w.category,
               w.purchase_date, w.warranty_end_date, w.description,
               w.warranty_card_image, w.created_at
        FROM warranty_items w
        JOIN users u ON w.user_id = u.user_id
        ORDER BY w.created_at DESC
    """)
    warranties = cur.fetchall()
    
    for warranty in warranties:
        pdf.add_page()
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, f'Warranty ID: {warranty[0]}', ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        pdf.set_font('Arial', '', 10)
        details = [
            ('Item', warranty[3]),
            ('Owner', warranty[1]),
            ('Email', warranty[2]),
            ('Category', warranty[4]),
            ('Purchase Date', warranty[5]),
            ('Expiry Date', warranty[6]),
            ('Created At', warranty[9])
        ]
        
        for label, value in details:
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(30, 8, f'{label}:', 0)
            pdf.set_font('Arial', '', 10)
            pdf.cell(0, 8, f'{value}', ln=True)
        
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, 'Description:', ln=True)
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 8, warranty[7] or 'No description provided')
        
        if warranty[8]:
            try:
                image = Image.open(io.BytesIO(warranty[8]))
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                img_path = f"temp_{warranty[0]}.jpg"
                image.save(img_path, 'JPEG', quality=85)
                pdf.image(img_path, x=10, y=pdf.get_y()+10, w=190)
                os.remove(img_path)
            except Exception as e:
                pdf.cell(0, 10, f"Error including warranty image: {str(e)}", ln=True)
    
    cur.close()
    conn.close()
    return pdf.output(dest='S').encode('latin-1')

def send_admin_report():
    
    user_id = st.session_state.get("user_id")
    user_email = get_user_email(user_id)

    if not user_email:
        st.error("Admin email not found")
        return
    
    sender = st.secrets["email"]["sender"]
    password = st.secrets["email"]["password"]
    
    email_body = """
    <div style="font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #eef1f8; padding: 32px 16px;">
        <div style="background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(30,41,59,0.15);">
            <div style="background: linear-gradient(135deg, #1e293b, #4f46e5); background-color: #1e293b; padding: 36px 24px; text-align: center;">
                <div style="display: inline-block; width: 56px; height: 56px; line-height: 56px; background-color: rgba(255,255,255,0.15); border-radius: 50%; font-size: 26px; margin-bottom: 14px;">&#128737;</div>
                <h1 style="color: #ffffff; font-size: 20px; margin: 0; font-weight: 600;">Admin Report</h1>
                <p style="color: rgba(255,255,255,0.8); font-size: 13px; margin: 4px 0 0;">Warranty Management System</p>
            </div>
            <div style="padding: 28px 24px; color: #1f2937;">
                <h2 style="color: #1e293b; font-size: 16px; margin: 0 0 12px;">System Overview</h2>
                <p style="font-size: 14px; color: #374151; margin: 0 0 16px;">Please find attached the following reports:</p>
                <div style="padding: 12px 16px; background-color: #f9fafb; border-radius: 10px; margin-bottom: 10px; border-left: 4px solid #4f46e5; font-size: 14px; color: #111827; font-weight: 600;">
                    &#128100; Complete Users Report <span style="color: #6b7280; font-weight: 400;">(PDF)</span>
                </div>
                <div style="padding: 12px 16px; background-color: #f9fafb; border-radius: 10px; border-left: 4px solid #4f46e5; font-size: 14px; color: #111827; font-weight: 600;">
                    &#128230; Complete Warranties Report <span style="color: #6b7280; font-weight: 400;">(PDF)</span>
                </div>
            </div>
            <div style="text-align: center; padding: 4px 24px 28px;">
                <p style="margin: 2px 0; font-size: 12px; color: #9ca3af;">This is an automated message, please do not reply to this email.</p>
            </div>
        </div>
    </div>
    """
    
    try:
        msg = MIMEMultipart("alternative")
        msg['Subject'] = 'Admin Reports - Warranty Management System'
        msg['From'] = f"Admin from Warranty System <{sender}>"
        msg['To'] = user_email
        
        msg.attach(MIMEText(email_body, 'html'))
        
        users_pdf = generate_admin_users_pdf()
        warranties_pdf = generate_admin_warranties_pdf()
        
        attachments = [
            ('users_report.pdf', users_pdf),
            ('warranties_report.pdf', warranties_pdf)
        ]
        
        for filename, pdf_bytes in attachments:
            attachment = MIMEApplication(pdf_bytes, _subtype='pdf')
            attachment.add_header('Content-Disposition', 'attachment', filename=filename)
            msg.attach(attachment)
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
            smtp_server.login(sender, password)
            smtp_server.sendmail(sender, user_email, msg.as_string())
        
        st.success("Admin reports sent to your email!")
    except Exception as e:
        st.error(f"Failed to send email: {str(e)}")

cols = st.columns([1,1,1,1,1,1])
with cols[0]:
    if st.button("🏠 Home"):
        st.switch_page("app.py")
with cols[1]:
    users_pdf = generate_admin_users_pdf()
    st.download_button(
        "👥 Users PDF",
        data=users_pdf,
        file_name="users_report.pdf",
        mime="application/pdf"
    )
with cols[2]:
    warranties_pdf = generate_admin_warranties_pdf()
    st.download_button(
        "📑 Warranties PDF",
        data=warranties_pdf,
        file_name="warranties_report.pdf",
        mime="application/pdf"
    )
with cols[3]:
    if st.button("📧 Email Reports"):
        send_admin_report()
with cols[4]:
    if st.button("🔄 Refresh"):
        st.rerun()
with cols[5]:
    if st.button("📤 Logout"):
        st.session_state.clear()
        st.rerun()


st.title("👑 Admin Dashboard")

total_users, new_users, roles = get_user_stats()
total_warranties, categories, expiring_soon = get_warranty_stats()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Users", total_users)
with col2:
    st.metric("New Users (7d)", new_users)
with col3:
    st.metric("Total Warranties", total_warranties)
with col4:
    st.metric("Expiring Soon", expiring_soon)

st.subheader("📊 Analytics")

col1, col2 = st.columns(2)
with col1:
    roles_df = pd.DataFrame(roles, columns=['Role', 'Count'])
    fig = px.pie(roles_df, values='Count', names='Role', title='User Roles Distribution')
    st.plotly_chart(fig, use_container_width=True)

with col2:
    categories_df = pd.DataFrame(categories, columns=['Category', 'Count'])
    fig = px.bar(categories_df, x='Category', y='Count', title='Warranties by Category')
    st.plotly_chart(fig, use_container_width=True)

st.subheader("📊 Detailed Analytics")

top_users, category_leaders = get_user_item_stats()

col1, col2 = st.columns(2)
with col1:
    st.subheader("Top Users by Items")
    users_df = pd.DataFrame(top_users, columns=['Username', 'Items'])
    fig = px.bar(users_df, x='Username', y='Items',
                 title='Top 10 Users by Number of Items',
                 labels={'Username': 'User', 'Items': 'Number of Items'})
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Category Leaders")
    leaders_df = pd.DataFrame(category_leaders, columns=['Username', 'Category', 'Count'])
    fig = px.bar(leaders_df, x='Category', y='Count', color='Username',
                 title='Category Leaders',
                 labels={'Count': 'Number of Items', 'Category': 'Category'})
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
