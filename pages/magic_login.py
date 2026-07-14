import streamlit as st
from app import verify_magic_link

st.title("Magic Link Login")

token = st.query_params.get("token")

if not token:
    st.error("Missing login token.")
    st.page_link("pages/login.py", label="Go to Login")
elif st.session_state.get("logged_in"):
    st.success(f"Already logged in as {st.session_state.get('username')}")
    st.page_link("app.py", label="Go to Home")
elif st.session_state.get("magic_login_done") == token:
    st.info("This link has already been used in this session.")
    st.page_link("app.py", label="Go to Home")
else:
    valid, username, role, error = verify_magic_link(token)
    if valid:
        st.session_state["logged_in"] = True
        st.session_state["username"] = username
        st.session_state["role"] = role
        st.session_state["magic_login_done"] = token
        st.success(f"Welcome, {username}! You're logged in.")
        st.page_link("app.py", label="Go to Home")
    else:
        st.error(error)
        st.page_link("pages/login.py", label="Go to Login")
