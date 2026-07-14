import streamlit as st
from app import signup_user, check_username_exists, check_email_exists, validate_password, verify_otp, is_valid_email
import time

st.title("Sign Up")

new_user = st.text_input("Username")
if new_user and check_username_exists(new_user):
    st.error("Username already exists")
    
email = st.text_input("Email")
if email:
    if not is_valid_email(email):
        st.error("Invalid email format")
    elif check_email_exists(email):
        st.error("Email already exists")
        
new_pass = st.text_input("Password", type="password")
if new_pass:
    password_error = validate_password(new_pass)
    if password_error:
        st.error(password_error)
        
confirm_pass = st.text_input("Confirm Password", type="password")
if confirm_pass and new_pass != confirm_pass:
    st.error("Passwords do not match")

if st.button("Sign Up"):
    if not any([
        check_username_exists(new_user),
        check_email_exists(email),
        validate_password(new_pass),
        new_pass != confirm_pass
    ]):
        if signup_user(new_user, email, new_pass, confirm_pass):
            st.session_state['verify_otp'] = True

if st.session_state.get('verify_otp'):
    if 'otp_attempts' not in st.session_state:
        st.session_state['otp_attempts'] = 0
        
    st.info(f"OTP sent to: {st.session_state['temp_user']['email']}")
    otp = st.text_input("Enter OTP")
    
    is_expired = time.time() > st.session_state['temp_user']['otp']['expiry']

    if is_expired:
        for key in ['verify_otp', 'temp_user', 'otp_attempts']:
            if key in st.session_state:
                del st.session_state[key]
        st.warning("Your OTP has expired and was cleared. Please sign up again to receive a new code.")
        st.rerun()

    verify_button = st.button("Verify OTP")

    if verify_button:
        success, message = verify_otp(otp)
        if success:
            st.success("Account created successfully!")
            st.page_link("pages/login.py", label="Go to Login")
            del st.session_state['verify_otp']
            del st.session_state['otp_attempts']
        else:
            if message == "OTP has expired":
                st.error(message)
            else:
                st.session_state['otp_attempts'] += 1
                remaining = 3 - st.session_state['otp_attempts']
                st.error(f"Invalid OTP. {remaining} attempts remaining.")
                if st.session_state['otp_attempts'] >= 3:
                    st.error("Maximum attempts reached. Please sign up again.")
                    del st.session_state['verify_otp']
                    del st.session_state['otp_attempts']
                    del st.session_state['temp_user']
                    st.rerun()

