import streamlit as st
import time
from app import login_user, request_login_otp, verify_login_otp, request_magic_link

st.title("Login")

tab_password, tab_otp, tab_magic = st.tabs(["🔒 Password", "📱 Email Code (2FA)", "✨ Magic Link"])

with tab_password:
    username = st.text_input("Username / Email", key="pwd_username")
    password = st.text_input("Password", type="password", key="pwd_password")

    if st.button("Login", key="pwd_login_btn"):
        valid, role, error = login_user(username, password)
        if valid:
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.session_state["role"] = role
            st.success(f"Welcome, {username} ({role})")
            st.page_link("app.py", label="Go to Home")
        else:
            st.error(error)

with tab_otp:
    st.caption("Log in without a password using a one-time code emailed to you.")

    if 'login_otp' not in st.session_state:
        otp_username = st.text_input("Username / Email", key="otp_username")
        if st.button("Send Code", key="send_otp_btn"):
            sent, message = request_login_otp(otp_username)
            if sent:
                st.success(message)
                st.rerun()
            else:
                st.error(message)
    else:
        st.info(f"Code sent to the email for: {st.session_state['login_otp']['username']}")
        code = st.text_input("Enter Code", key="otp_code")

        is_expired = time.time() > st.session_state['login_otp']['otp']['expiry']

        col1, col2 = st.columns([1, 4])
        with col1:
            verify_clicked = st.button("Verify", key="verify_otp_btn", disabled=is_expired)
        with col2:
            if is_expired:
                st.error("Code expired. Please request a new one.")
            if st.button("Cancel", key="cancel_otp_btn"):
                del st.session_state['login_otp']
                st.rerun()

        if verify_clicked:
            valid, otp_result_username, role, error = verify_login_otp(code)
            if valid:
                st.session_state["logged_in"] = True
                st.session_state["username"] = otp_result_username
                st.session_state["role"] = role
                st.success(f"Welcome, {otp_result_username} ({role})")
                st.page_link("app.py", label="Go to Home")
            else:
                st.error(error)

with tab_magic:
    st.caption("We'll email you a secure link that logs you in instantly. No password needed.")
    magic_email = st.text_input("Email", key="magic_email")
    if st.button("Send Magic Link", key="send_magic_btn"):
        sent, message = request_magic_link(magic_email)
        if sent:
            st.success(message)
        else:
            st.error(message)
