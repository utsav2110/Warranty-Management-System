import streamlit as st
import psycopg
import bcrypt
import re
import random
import smtplib
import time
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlparse
from datetime import datetime, timedelta
from PIL import Image
from fpdf import FPDF
import io
import os
import secrets
from email.mime.application import MIMEApplication
import plotly.express as px
import base64
import streamlit.components.v1 as components

CATEGORIES = [
    "Electronics", "Appliances", "Vehicles", "Furniture", 
    "Tools", "Mobile Devices", "Computers", "Other"
]

def add_warranty_item(user_id, item_name, category, purchase_date, warranty_end_date, warranty_image, description):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """INSERT INTO warranty_items (user_id, item_name, category, purchase_date, warranty_end_date, warranty_card_image, description)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (user_id, item_name, category, purchase_date, warranty_end_date, warranty_image, description)
    )
    warranty_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()
    return warranty_id

def add_attachment(warranty_id, file_data, file_name, mime_type, attachment_type):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO warranty_attachments (warranty_id, attachment_type, file_name, mime_type, file_data)
           VALUES (%s, %s, %s, %s, %s)
           RETURNING attachment_id""",
        (warranty_id, attachment_type, file_name, mime_type, file_data)
    )
    attachment_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return attachment_id

def get_attachments(warranty_id, attachment_type=None):
    conn = get_conn()
    cur = conn.cursor()
    if attachment_type:
        cur.execute(
            """SELECT attachment_id, warranty_id, attachment_type, file_name, mime_type, file_data, uploaded_at
               FROM warranty_attachments WHERE warranty_id = %s AND attachment_type = %s
               ORDER BY uploaded_at""",
            (warranty_id, attachment_type)
        )
    else:
        cur.execute(
            """SELECT attachment_id, warranty_id, attachment_type, file_name, mime_type, file_data, uploaded_at
               FROM warranty_attachments WHERE warranty_id = %s
               ORDER BY uploaded_at""",
            (warranty_id,)
        )
    attachments = cur.fetchall()
    cur.close()
    conn.close()
    return attachments

def delete_attachment(attachment_id, warranty_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """DELETE FROM warranty_attachments
           WHERE attachment_id = %s AND warranty_id = %s""",
        (attachment_id, warranty_id)
    )
    deleted = cur.rowcount > 0
    conn.commit()
    cur.close()
    conn.close()
    return deleted

def update_warranty_item(warranty_id, user_id, item_name, category, purchase_date, warranty_end_date, description, warranty_image=None):
    conn = get_conn()
    cur = conn.cursor()

    if warranty_image:
        cur.execute(
            """UPDATE warranty_items
               SET item_name = %s, category = %s, purchase_date = %s,
                   warranty_end_date = %s, description = %s, warranty_card_image = %s
               WHERE id = %s AND user_id = %s""",
            (item_name, category, purchase_date, warranty_end_date, description, warranty_image, warranty_id, user_id)
        )
    else:
        cur.execute(
            """UPDATE warranty_items
               SET item_name = %s, category = %s, purchase_date = %s,
                   warranty_end_date = %s, description = %s
               WHERE id = %s AND user_id = %s""",
            (item_name, category, purchase_date, warranty_end_date, description, warranty_id, user_id)
        )

    updated = cur.rowcount > 0
    conn.commit()
    cur.close()
    conn.close()
    return updated

def delete_warranty_item(warranty_id, user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM warranty_items WHERE id = %s AND user_id = %s",
        (warranty_id, user_id)
    )
    deleted = cur.rowcount > 0
    conn.commit()
    cur.close()
    conn.close()
    return deleted

def get_all_warranties():
    if not st.session_state.get("logged_in") or st.session_state.get("role") == "admin":
        return []
    
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM warranty_items 
        WHERE user_id = %s 
        ORDER BY warranty_end_date
    """, (st.session_state.get("user_id"),))
    items = cur.fetchall()
    cur.close()
    conn.close()
    return items

def search_warranties(search_term="", category=None, date_filter=None):
    if not st.session_state.get("logged_in") or st.session_state.get("role") == "admin":
        return []
    
    conn = get_conn()
    cur = conn.cursor()
    
    query = "SELECT * FROM warranty_items WHERE user_id = %s"
    params = [st.session_state.get("user_id")]
    
    if search_term:
        query += " AND (item_name ILIKE %s OR description ILIKE %s)"
        search_pattern = f"%{search_term}%"
        params.extend([search_pattern, search_pattern])
    
    if category and category != "All":
        query += " AND category = %s"
        params.append(category)
    
    if date_filter == "Expiring Soon":
        query += " AND warranty_end_date <= %s"
        params.append((datetime.now() + timedelta(days=7)).date())
    
    query += " ORDER BY warranty_end_date"
    
    cur.execute(query, params)
    items = cur.fetchall()
    cur.close()
    conn.close()
    return items

def validate_dates(purchase_date, warranty_end_date):
    if warranty_end_date <= purchase_date:
        return False
    return True

def get_user_email(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT email FROM users WHERE user_id = %s", (user_id,))
    email = cur.fetchone()
    cur.close()
    conn.close()
    return email[0] if email else None

def check_expiring_warranties():
    user_id = st.session_state.get("user_id")
    user_email = get_user_email(user_id)
    
    if not user_email:
        st.error("Could not find user email.")
        return
    
    sender = st.secrets["email"]["sender"]
    password = st.secrets["email"]["password"]
    
    warranties = get_all_warranties()
    if not warranties:
        st.warning("No warranties found to send.")
        return
    
    email_body = f"""
    <div style="font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #eef1f8; padding: 32px 16px;">
        <div style="background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(79,70,229,0.12);">
            <div style="background: linear-gradient(135deg, #4f46e5, #7c3aed); background-color: #4f46e5; padding: 36px 24px; text-align: center;">
                <div style="display: inline-block; width: 56px; height: 56px; line-height: 56px; background-color: rgba(255,255,255,0.15); border-radius: 50%; font-size: 26px; margin-bottom: 14px;">&#128203;</div>
                <h1 style="color: #ffffff; font-size: 20px; margin: 0; font-weight: 600;">Your Warranty Report</h1>
                <p style="color: rgba(255,255,255,0.85); font-size: 13px; margin: 4px 0 0;">Complete list of your registered warranties</p>
            </div>
            <div style="padding: 28px 24px; color: #1f2937;">
                <div style="text-align: center; background-color: #f5f3ff; border-radius: 12px; padding: 16px; margin-bottom: 22px;">
                    <div style="font-size: 28px; font-weight: 700; color: #4f46e5;">{len(warranties)}</div>
                    <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #8b8fa3; font-weight: 600;">Total Warranties</div>
                </div>
    """

    for warranty in warranties:
        email_body += f"""
                <div style="padding: 14px 16px; background-color: #f9fafb; border-radius: 10px; margin-bottom: 10px; border-left: 4px solid #7c3aed;">
                    <div style="font-size: 15px; font-weight: 600; color: #111827; margin-bottom: 6px;">&#128230; {warranty[2]}</div>
                    <div style="font-size: 13px; color: #6b7280;">
                        <span style="display: inline-block; background-color: #ede9fe; color: #5b21b6; padding: 2px 10px; border-radius: 12px; font-size: 11.5px; font-weight: 600; margin-right: 8px;">{warranty[3]}</span>
                        Expires: <strong>{warranty[5]}</strong>
                    </div>
                </div>
        """

    email_body += """
            </div>
            <div style="text-align: center; padding: 4px 24px 28px;">
                <p style="margin: 2px 0; font-size: 12px; color: #9ca3af;">This is an automated message, please do not reply to this email.</p>
            </div>
        </div>
    </div>
    """
    
    pdf_bytes = generate_warranty_pdf()
        
    try:
        msg = MIMEMultipart("alternative")
        msg['Subject'] = 'Complete Warranty Report'
        msg['From'] = f"Warranty System <{sender}>"
        msg['To'] = user_email
        
        msg.attach(MIMEText(email_body, 'html'))
        
        pdf_attachment = MIMEApplication(pdf_bytes, _subtype='pdf')
        pdf_attachment.add_header('Content-Disposition', 'attachment',  filename='warranty_report.pdf')
        msg.attach(pdf_attachment)
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
            smtp_server.login(sender, password)
            smtp_server.sendmail(sender, user_email, msg.as_string())
            
        st.success("Complete warranty report sent to your email!")
            
    except Exception as e:
        st.error(f"Failed to send email: {str(e)}")

def render_pdf_preview(pdf_bytes, height=600):
    """Embed a PDF inline so the user can view it without downloading first."""
    base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
    components.html(
        f'<iframe src="data:application/pdf;base64,{base64_pdf}" '
        f'width="100%" height="{height}" style="border: none;"></iframe>',
        height=height,
    )

def generate_warranty_pdf():
    warranties = get_all_warranties()
    pdf = FPDF()
    
    for warranty in warranties:
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, f'Item: {warranty[2]}', ln=True)  
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, f'Category: {warranty[3]}', ln=True)  
        pdf.cell(0, 10, f'Purchase Date: {warranty[4]}', ln=True)  
        pdf.cell(0, 10, f'Warranty End Date: {warranty[5]}', ln=True)  
        pdf.cell(0, 10, f'Description: {warranty[7]}', ln=True)  
        
        if warranty[6]:  
            try:
                image = Image.open(io.BytesIO(warranty[6]))
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                    
                img_path = f"temp_{warranty[0]}.jpg"
                image.save(img_path, 'JPEG', quality=85)
                
                try:
                    pdf.image(img_path, x=10, y=100, w=190)
                finally:
                    if os.path.exists(img_path):
                        os.remove(img_path)
            except Exception as e:
                pdf.cell(0, 10, f"Error including warranty image: {str(e)}", ln=True)
    
    return pdf.output(dest='S').encode('latin1')

def send_email(to_email, subject, body):
    sender_email = st.secrets["email"]["sender"]
    sender_password = st.secrets["email"]["password"]
    
    message = MIMEMultipart("alternative")
    message["From"] = f"Authentication System <{sender_email}>"
    message["To"] = to_email
    message["Subject"] = subject
    
    html_content = get_email_template(subject, body)
    message.attach(MIMEText(body, "plain"))  
    message.attach(MIMEText(html_content, "html"))  
    
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(message)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

def get_email_template(subject, content):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ margin: 0; padding: 0; background-color: #eef1f8; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
            .wrapper {{ width: 100%; background-color: #eef1f8; padding: 32px 16px; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(79,70,229,0.12); }}
            .header {{ background: linear-gradient(135deg, #4f46e5, #7c3aed); background-color: #4f46e5; padding: 36px 24px; text-align: center; }}
            .header .badge {{ display: inline-block; width: 56px; height: 56px; line-height: 56px; background-color: rgba(255,255,255,0.15); border-radius: 50%; font-size: 26px; margin-bottom: 14px; }}
            .header h1 {{ color: #ffffff; font-size: 20px; margin: 0; font-weight: 600; }}
            .header p {{ color: rgba(255,255,255,0.85); font-size: 13px; margin: 4px 0 0; letter-spacing: 0.3px; }}
            .content {{ padding: 32px 28px; color: #1f2937; font-size: 15px; line-height: 1.6; }}
            .content p {{ margin: 0 0 14px; }}
            .otp-box {{ text-align: center; margin: 24px 0; }}
            .otp-label {{ text-transform: uppercase; font-size: 11px; letter-spacing: 1.5px; color: #8b8fa3; font-weight: 600; margin-bottom: 10px; }}
            .otp-code {{ display: inline-block; background-color: #f5f3ff; border: 1.5px dashed #7c3aed; border-radius: 12px; padding: 16px 28px; font-size: 32px; font-weight: 700; letter-spacing: 10px; color: #4f46e5; font-family: 'Courier New', monospace; }}
            .expiry-note {{ display: inline-block; margin-top: 14px; background-color: #fff7ed; color: #c2410c; font-size: 12.5px; padding: 6px 14px; border-radius: 20px; font-weight: 600; }}
            .button {{ display: inline-block; padding: 14px 32px; background: linear-gradient(135deg, #4f46e5, #7c3aed); background-color: #4f46e5; color: #ffffff !important; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px; box-shadow: 0 4px 12px rgba(79,70,229,0.35); }}
            .button:visited {{ color: #ffffff !important; }}
            .divider {{ height: 1px; background-color: #eef0f5; margin: 0 28px; }}
            .footer {{ text-align: center; padding: 22px 24px 30px; }}
            .footer .brand {{ font-size: 12.5px; color: #6b7280; font-weight: 600; margin-bottom: 6px; }}
            .footer p {{ margin: 2px 0; font-size: 12px; color: #9ca3af; }}
        </style>
    </head>
    <body>
        <div class="wrapper">
            <div class="container">
                <div class="header">
                    <div class="badge">&#128737;</div>
                    <h1>{subject}</h1>
                    <p>Warranty Management System</p>
                </div>
                <div class="content">
                    {content}
                </div>
                <div class="divider"></div>
                <div class="footer">
                    <p class="brand">&#128737; Warranty Management System</p>
                    <p>This is an automated message &mdash; please don't reply to this email.</p>
                    <p>If you didn't request this, you can safely ignore it.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

def get_otp_block(code):
    return f"""
    <div class="otp-box">
        <div class="otp-label">Your verification code</div>
        <div class="otp-code">{code}</div>
        <div><span class="expiry-note">&#9201; Expires in 10 minutes</span></div>
    </div>
    """

def generate_otp():
    return {
        'code': str(random.randint(100000, 999999)),
        'expiry': time.time() + 600 
    }

def get_conn():
    return psycopg.connect(
        host=st.secrets["postgres"]["host"],
        port=st.secrets["postgres"]["port"],
        dbname=st.secrets["postgres"]["database"], 
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"],
        sslmode="require"  
    )

def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def signup_user(username, email, password, confirm_password):
    if password != confirm_password:
        st.warning("Passwords do not match.")
        return False
    
    if len(password) < 6:
        st.warning("Password should be at least 6 characters.")
        return False
    
    if not is_valid_email(email):
        st.warning("Invalid email format.")
        return False

    otp = generate_otp()
    email_content = f"""
    <p>Hello <strong>{username}</strong>,</p>
    <p>Thanks for signing up! Use the verification code below to confirm your email address.</p>
    {get_otp_block(otp['code'])}
    <p style="font-size: 13px; color: #6b7280;">For your security, please never share this code with anyone.</p>
    """
    if send_email(email, "Email Verification", email_content):
        st.session_state['temp_user'] = {
            'username': username,
            'email': email,
            'password': password,
            'otp': otp
        }
        return True
    return False

def verify_otp(entered_otp):
    if 'temp_user' not in st.session_state:
        return False, "Session expired"
    
    stored_otp = st.session_state['temp_user']['otp']
    
    if time.time() > stored_otp['expiry']:
        del st.session_state['temp_user']
        return False, "OTP has expired"
    
    if entered_otp == stored_otp['code']:
        user = st.session_state['temp_user']
        hashed = bcrypt.hashpw(user['password'].encode(), bcrypt.gensalt()).decode()
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO users (username, email, password_hash)
                VALUES (%s, %s, %s)
            """, (user['username'], user['email'], hashed))
            conn.commit()
            cur.close()
            conn.close()
            del st.session_state['temp_user']
            return True, "Success"
        except Exception as e:
            return False, f"Signup failed: {e}"
    return False, "Invalid OTP"

def login_user(username, password):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, password_hash, role 
            FROM users 
            WHERE username = %s OR email = %s
        """, (username, username))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            return False, None, "User not found"
        
        if not bcrypt.checkpw(password.encode(), row[1].encode()):
            return False, None, "Incorrect password"
        
        st.session_state["user_id"] = row[0]  
        return True, row[2], None
    except Exception as e:
        st.error(f"Login failed: {e}")
        return False, None, str(e)

def request_login_otp(username_or_email):
    """Send a one-time code to log in without a password (email-based 2FA login)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, username, email, role FROM users
        WHERE username = %s OR email = %s
    """, (username_or_email, username_or_email))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return False, "User not found"

    user_id, username, email, role = row
    otp = generate_otp()
    email_content = f"""
    <p>Hello <strong>{username}</strong>,</p>
    <p>Use the verification code below to securely log in to your account.</p>
    {get_otp_block(otp['code'])}
    <p style="font-size: 13px; color: #6b7280;">If you didn't request this, you can safely ignore this email.</p>
    """
    if send_email(email, "Your Login Verification Code", email_content):
        st.session_state['login_otp'] = {
            'user_id': user_id,
            'username': username,
            'role': role,
            'otp': otp
        }
        return True, "Verification code sent to your email"
    return False, "Failed to send verification code"

def verify_login_otp(entered_otp):
    if 'login_otp' not in st.session_state:
        return False, None, None, "Session expired. Please request a new code."

    data = st.session_state['login_otp']

    if time.time() > data['otp']['expiry']:
        del st.session_state['login_otp']
        return False, None, None, "Code has expired"

    if entered_otp != data['otp']['code']:
        return False, None, None, "Invalid code"

    username = data['username']
    role = data['role']
    st.session_state["user_id"] = data['user_id']
    del st.session_state['login_otp']
    return True, username, role, None

def cleanup_expired_magic_links():
    """Purge used/expired magic-link tokens so the table doesn't grow unbounded."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM magic_link_tokens WHERE used = TRUE OR expires_at < %s",
        (datetime.now(),)
    )
    conn.commit()
    cur.close()
    conn.close()

def generate_magic_link_token(user_id):
    cleanup_expired_magic_links()

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(minutes=15)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO magic_link_tokens (user_id, token, expires_at)
           VALUES (%s, %s, %s)""",
        (user_id, token, expires_at)
    )
    conn.commit()
    cur.close()
    conn.close()
    return token

def request_magic_link(email):
    """Email a one-click, single-use login link (passwordless login)."""
    if not is_valid_email(email):
        return False, "Invalid email format"

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username FROM users WHERE email = %s", (email,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return False, "Email not found in our records"

    user_id, username = row
    token = generate_magic_link_token(user_id)
    base_url = st.secrets.get("app", {}).get("base_url", "https://warranty-tracking-system.streamlit.app")
    magic_url = f"{base_url}/magic_login?token={token}"

    email_content = f"""
    <p>Hello <strong>{username}</strong>,</p>
    <p>Click the button below to securely log in &mdash; no password needed.</p>
    <div style="text-align: center; margin: 28px 0;">
        <a class="button" href="{magic_url}">&#128274; Log In Securely</a>
    </div>
    <p style="font-size: 13px; color: #6b7280;">Or paste this link into your browser:<br>
    <a href="{magic_url}" style="color: #4f46e5; word-break: break-all;">{magic_url}</a></p>
    <div style="margin-top: 20px; padding: 12px 16px; background-color: #fff7ed; border-radius: 8px; font-size: 12.5px; color: #c2410c;">
        &#9201; This link expires in 15 minutes and can only be used once.
    </div>
    <p style="font-size: 13px; color: #6b7280; margin-top: 16px;">If you didn't request this, you can safely ignore this email.</p>
    """
    if send_email(email, "Your Magic Login Link", email_content):
        return True, "Magic link sent! Check your email."
    return False, "Failed to send magic link email"

def verify_magic_link(token):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.token_id, t.user_id, t.expires_at, t.used, u.username, u.role
        FROM magic_link_tokens t
        JOIN users u ON t.user_id = u.user_id
        WHERE t.token = %s
    """, (token,))
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return False, None, None, "Invalid or unknown login link"

    token_id, user_id, expires_at, used, username, role = row

    if used:
        cur.close()
        conn.close()
        return False, None, None, "This login link has already been used"

    if datetime.now() > expires_at:
        cur.close()
        conn.close()
        return False, None, None, "This login link has expired"

    cur.execute("UPDATE magic_link_tokens SET used = TRUE WHERE token_id = %s", (token_id,))
    conn.commit()
    cur.close()
    conn.close()

    st.session_state["user_id"] = user_id
    return True, username, role, None

def change_password(user_id, current_password, new_password, confirm_password):
    if new_password != confirm_password:
        return False, "New passwords do not match"

    password_error = validate_password(new_password)
    if password_error:
        return False, password_error

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE user_id = %s", (user_id,))
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return False, "User not found"

    if not bcrypt.checkpw(current_password.encode(), row[0].encode()):
        cur.close()
        conn.close()
        return False, "Current password is incorrect"

    if bcrypt.checkpw(new_password.encode(), row[0].encode()):
        cur.close()
        conn.close()
        return False, "New password must be different from your current password"

    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    cur.execute("UPDATE users SET password_hash = %s WHERE user_id = %s", (hashed, user_id))
    conn.commit()
    cur.close()
    conn.close()
    return True, "Password changed successfully"

def check_username_exists(username):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE username = %s", (username,))
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count > 0
    except Exception:
        return False

def check_email_exists(email):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE email = %s", (email,))
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count > 0
    except Exception:
        return False

def validate_password(password):
    if len(password) < 6:
        return "Password must be at least 6 characters"
    if not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one number"
    return None

def get_category_stats():
    warranties = get_all_warranties()
    category_counts = {}
    for warranty in warranties:
        category = warranty[3]
        category_counts[category] = category_counts.get(category, 0) + 1
    return category_counts

def get_expiry_timeline():
    warranties = get_all_warranties()
    today = datetime.now().date()
    timelines = {
        "Expired": 0,
        "This Week": 0,
        "This Month": 0,
        "3 Months": 0,
        "6 Months": 0,
        "Later": 0
    }
    
    for warranty in warranties:
        expiry_date = warranty[5]
        days_until = (expiry_date - today).days
        
        if days_until < 0:
            timelines["Expired"] += 1
        elif days_until <= 7:
            timelines["This Week"] += 1
        elif days_until <= 30:
            timelines["This Month"] += 1
        elif days_until <= 90:
            timelines["3 Months"] += 1
        elif days_until <= 180:
            timelines["6 Months"] += 1
        else:
            timelines["Later"] += 1
            
    return timelines

def get_notification_items(user_id=None, days=7):
    if user_id is None:
        user_id = st.session_state.get("user_id")
    if not user_id:
        return []

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, item_name, category, warranty_end_date
        FROM warranty_items
        WHERE user_id = %s AND warranty_end_date <= %s
        ORDER BY warranty_end_date
    """, (user_id, (datetime.now() + timedelta(days=days)).date()))
    items = cur.fetchall()
    cur.close()
    conn.close()
    return items

def render_notification_bell():
    if not st.session_state.get("logged_in") or st.session_state.get("role") == "admin":
        return

    items = get_notification_items()
    count = len(items)
    label = f"🔔 {count}" if count else "🔔"

    with st.popover(label):
        st.write("### Notifications")
        if not items:
            st.caption("No expiring warranties. You're all caught up!")
        else:
            today = datetime.now().date()
            for item_id, item_name, category, warranty_end_date in items:
                days_until = (warranty_end_date - today).days
                if days_until < 0:
                    status = f"⛔ Expired {abs(days_until)} day(s) ago"
                elif days_until == 0:
                    status = "⚠️ Expires today"
                else:
                    status = f"⏳ Expires in {days_until} day(s)"

                st.markdown(f"**{item_name}** ({category})  \n{status}")
                if st.button("View", key=f"notif_view_{item_id}", use_container_width=True):
                    st.session_state.selected_warranty = item_id
                    st.switch_page("pages/warranty_details.py")
                st.markdown("---")

def get_current_route():
    try:
        query_params = st.query_params
        page = query_params.get("page", "home")
        path = urlparse(page).path
        return path
    except:
        return "home"

def navigate_to(page):
    st.query_params['page'] = page

def get_data_as_df(query):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query)
    data = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()
    return pd.DataFrame(data, columns=columns)

st.set_page_config(page_title="Warranty Expiry Tracking System", page_icon="🔐", layout="wide")

with st.container():
    if not st.session_state.get("logged_in"):
        cols = st.columns([1,1,1,1,1])
        with cols[0]:
            if st.button("🏠 Home"):
                st.query_params['page'] = 'home'
                st.rerun()
        with cols[1]:
            if st.button("👤 Login"):
                st.switch_page("pages/login.py")
        with cols[2]:
            if st.button("📝 Sign Up"):
                st.switch_page("pages/signup.py")
        with cols[3]:
            if st.button("🔑 Forgot Password"):
                st.switch_page("pages/forgot_password.py")
    else:
        if st.session_state["role"] == "admin":
            cols = st.columns([1,1,1,1])
            with cols[0]:
                if st.button("🏠 Home"):
                    st.query_params['page'] = 'home'
                    st.rerun()
            with cols[1]:
                if st.button("👑 Dashboard"):
                    st.switch_page("pages/admin_dashboard.py")
            with cols[2]:
                if st.button("⚙️ Account"):
                    st.switch_page("pages/account_settings.py")
            with cols[3]:
                if st.button("📤 Logout"):
                    st.session_state.clear()
                    st.rerun()
        else:
            cols = st.columns([1,1,1,1,1,1])
            with cols[0]:
                if st.button("🏠 Home"):
                    st.query_params['page'] = 'home'
                    st.rerun()
            with cols[1]:
                if st.button("➕ Add Warranty"):
                    st.switch_page("pages/add_warranty.py")
            with cols[2]:
                if st.button("📋 View Warranties"):
                    st.switch_page("pages/warranties.py")
            with cols[3]:
                if st.button("⚙️ Account"):
                    st.switch_page("pages/account_settings.py")
            with cols[4]:
                if st.button("📤 Logout"):
                    st.session_state.clear()
                    st.rerun()
            with cols[5]:
                render_notification_bell()

st.markdown("---")

st.title("Welcome to Warranty Management System")
if st.session_state.get("logged_in"):
    st.info(f"Logged in as: {st.session_state['username']}")
    
    if st.session_state["role"] == "admin":
        st.warning("Admin users don't have access to warranty management features.")
        
        st.subheader("👥 All Registered Users")
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("SELECT user_id, username, email, role, created_at FROM users")
            users = cur.fetchall()
            cur.close()
            conn.close()

            df = pd.DataFrame(users, columns=["ID", "Username", "Email", "Role", "Created At"])
            st.dataframe(df)
        except Exception as e:
            st.error(f"Error fetching users: {e}")

        st.subheader("📜 Warranty Items Overview")
        try:
            warranties_query = """
                SELECT 
                    w.id as "ID",
                    u.username as "Owner",
                    w.item_name as "Item",
                    w.category as "Category",
                    to_char(w.purchase_date, 'YYYY-MM-DD') as "Purchase Date",
                    to_char(w.warranty_end_date, 'YYYY-MM-DD') as "Expiry Date",
                    to_char(w.created_at, 'YYYY-MM-DD HH24:MI') as "Created At"
                FROM warranty_items w
                JOIN users u ON w.user_id = u.user_id
                ORDER BY w.created_at DESC
            """
            warranties_df = get_data_as_df(warranties_query)
            st.dataframe(warranties_df, use_container_width=True)
        except Exception as e:
            st.error(f"Error fetching warranties: {e}")

    else:

        st.success("🎯 Welcome to Your Warranty Dashboard")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Category Distribution")
            category_stats = get_category_stats()
            if category_stats:
                fig = px.pie(
                    values=list(category_stats.values()),
                    names=list(category_stats.keys()),
                    hole=0.3
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Add warranties to see category distribution")
                
        with col2:
            st.subheader("⏳ Expiry Timeline")
            timeline_stats = get_expiry_timeline()
            if any(timeline_stats.values()):
                fig = px.bar(
                    x=list(timeline_stats.keys()),
                    y=list(timeline_stats.values()),
                    labels={'x': 'Timeline', 'y': 'Number of Warranties'}
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Add warranties to see expiry timeline")
        
        st.subheader("📈 Quick Stats")
        col1, col2, col3 = st.columns(3)
        with col1:
            total_warranties = len(get_all_warranties())
            st.metric("Total Warranties", total_warranties)
        with col2:
            expiring_soon = len(search_warranties(date_filter="Expiring Soon"))
            st.metric("Expiring Soon", expiring_soon)
        with col3:
            active_categories = len(get_category_stats())
            st.metric("Active Categories", active_categories)
        
        st.subheader("🆕 Recent Warranties")
        recent = search_warranties()[:3]
        if recent:
            cols = st.columns(3)
            for idx, warranty in enumerate(recent):
                with cols[idx]:
                    with st.container():
                        st.markdown("""
                        <style>
                            .warranty-card {
                                padding: 1rem;
                                border-radius: 0.5rem;
                                border: 1px solid #ddd;
                                margin: 0.5rem 0;
                            }
                        </style>
                        """, unsafe_allow_html=True)
                        
                        st.markdown(f"""
                        <div class="warranty-card">
                            <h3>{warranty[2]}</h3>
                            <p><strong>Category:</strong> {warranty[3]}</p>
                            <p><strong>Expires:</strong> {warranty[5]}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if warranty[6]: 
                            try:
                                image = Image.open(io.BytesIO(warranty[6]))
                                if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                                    image = image.convert('RGBA')
                                else:
                                    image = image.convert('RGB')
                                st.image(image, use_container_width=True)
                            except Exception as e:
                                st.error(f"Error loading image: {str(e)}")
                                
                        if st.button("View Details", key=f"view_{warranty[0]}"):
                            st.session_state.selected_warranty = warranty[0]
                            st.switch_page("pages/warranty_details.py")
        else:
            st.info("No warranties added yet. Click 'Add Warranty' to get started!")
else:
    st.write("Please login to access your warranty dashboard.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Login Now", use_container_width=True):
            st.switch_page("pages/login.py")
    with col2:
        if st.button("Sign Up", use_container_width=True):
            st.switch_page("pages/signup.py")
