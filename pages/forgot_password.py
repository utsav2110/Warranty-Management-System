import streamlit as st
from app import check_email_exists, generate_otp, send_email, validate_password , is_valid_email, get_otp_block
import bcrypt
from app import get_conn
import time

st.title("Reset Password")

if 'reset_step' not in st.session_state:
    st.session_state['reset_step'] = 'email'

if st.session_state['reset_step'] == 'email':
    email = st.text_input("Enter your email")
    email_valid = False
    
    if email:
        if not is_valid_email(email):
            st.error("Invalid email format")
        elif not check_email_exists(email):
            st.error("Email not found in our records")
        else:
            email_valid = True
    
    if st.button("Send OTP", disabled=not email_valid):
        otp = generate_otp()
        email_content = f"""
        <p>Hello,</p>
        <p>We received a request to reset your password. Use the verification code below to proceed.</p>
        {get_otp_block(otp['code'])}
        <p style="font-size: 13px; color: #6b7280;">If you didn't request this, you can safely ignore this email.</p>
        """
        if send_email(email, "Password Reset Request", email_content):
            st.session_state['reset_otp'] = otp
            st.session_state['reset_email'] = email
            st.session_state['reset_step'] = 'otp'
            st.session_state['otp_attempts'] = 0
            st.success("OTP sent to your email")
            st.rerun()

elif st.session_state['reset_step'] == 'otp':
    st.info(f"OTP sent to: {st.session_state['reset_email']}")
    otp = st.text_input("Enter OTP")
    
    is_expired = time.time() > st.session_state['reset_otp']['expiry']

    if is_expired:
        for key in ['reset_step', 'reset_otp', 'reset_email', 'otp_attempts']:
            if key in st.session_state:
                del st.session_state[key]
        st.warning("Your OTP has expired and was cleared. Please start the password reset again.")
        st.rerun()

    verify_button = st.button("Verify OTP")

    if verify_button:
        if st.session_state['otp_attempts'] >= 3:
            st.error("Maximum attempts reached. Please start over.")
            for key in ['reset_step', 'reset_otp', 'reset_email', 'otp_attempts']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        
        if otp == st.session_state['reset_otp']['code']:
            st.session_state['reset_step'] = 'password'
            st.success("OTP verified successfully!")
            st.rerun()
        else:
            st.session_state['otp_attempts'] += 1
            remaining = 3 - st.session_state['otp_attempts']
            st.error(f"Invalid OTP. {remaining} attempts remaining.")

elif st.session_state['reset_step'] == 'password':
    st.success("OTP Verified - Set New Password")
    
    new_pass = st.text_input("New Password", type="password")
    password_error = validate_password(new_pass) if new_pass else None
    if password_error:
        st.error(password_error)
        
    confirm_pass = st.text_input("Confirm New Password", type="password")
    if confirm_pass and new_pass != confirm_pass:
        st.error("Passwords do not match")
        
    if st.button("Reset Password"):
        if password_error:
            st.error(password_error)
        elif new_pass != confirm_pass:
            st.error("Passwords do not match")
        else:
            hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()
            try:
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE users
                    SET password_hash = %s, reset_token = NULL
                    WHERE email = %s
                """, (hashed, st.session_state['reset_email']))
                conn.commit()
                cur.close()
                conn.close()
                st.success("Password reset successful!")
                
                for key in ['reset_step', 'reset_otp', 'reset_email', 'otp_attempts']:
                    if key in st.session_state:
                        del st.session_state[key]
                        
                st.page_link("pages/login.py", label="Go to Login")
            except Exception as e:
                st.error(f"Error: {e}")
