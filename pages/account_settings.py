import streamlit as st
from app import change_password

st.title("Account Settings")

if not st.session_state.get("logged_in"):
    st.warning("Please log in to access account settings.")
    st.page_link("pages/login.py", label="Go to Login")
else:
    st.subheader(f"Signed in as {st.session_state['username']}")

    st.markdown("### 🔑 Change Password")
    current_password = st.text_input("Current Password", type="password", key="cp_current")
    new_password = st.text_input("New Password", type="password", key="cp_new")
    confirm_password = st.text_input("Confirm New Password", type="password", key="cp_confirm")

    if st.button("Change Password"):
        if not current_password or not new_password or not confirm_password:
            st.error("Please fill in all fields.")
        else:
            success, message = change_password(
                st.session_state["user_id"], current_password, new_password, confirm_password
            )
            if success:
                st.success(message)
            else:
                st.error(message)
