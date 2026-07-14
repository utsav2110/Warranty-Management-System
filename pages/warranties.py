import streamlit as st
from app import get_all_warranties, search_warranties, generate_warranty_pdf, check_expiring_warranties, Image, io, CATEGORIES, render_notification_bell, render_pdf_preview

if st.session_state.get("logged_in"):
    cols = st.columns([1,1,1,1,1,1,1])
    with cols[0]:
        if st.button("🏠 Home"):
            st.switch_page("app.py")
    with cols[1]:
        if st.button("➕ Add Warranty"):
            st.switch_page("pages/add_warranty.py")
    with cols[2]:
        if st.button("📋 View Warranties"):
            st.rerun()
    with cols[3]:
        if st.button("📑 Export PDF"):
            st.session_state["pdf_preview_bytes"] = generate_warranty_pdf()
    with cols[4]:
        if st.button("📧 Mail Report"):
            check_expiring_warranties()
    with cols[5]:
        if st.button("📤 Logout"):
            st.session_state.clear()
            st.rerun()
    with cols[6]:
        render_notification_bell()
    st.markdown("---")

    if st.session_state.get("pdf_preview_bytes"):
        st.write("### 📑 Warranty Report Preview")
        render_pdf_preview(st.session_state["pdf_preview_bytes"])
        dl_col, close_col, _ = st.columns([1, 1, 4])
        with dl_col:
            st.download_button(
                label="Download PDF",
                data=st.session_state["pdf_preview_bytes"],
                file_name="warranty_report.pdf",
                mime="application/pdf",
                key="navbar_pdf"
            )
        with close_col:
            if st.button("Close Preview"):
                del st.session_state["pdf_preview_bytes"]
                st.rerun()
        st.markdown("---")
st.title("My Warranties")

if not st.session_state.get("logged_in"):
    st.warning("Please login to view your warranties")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Login Now", use_container_width=True,key="1"):
            st.switch_page("pages/login.py")
    with col2:
        if st.button("Sign Up", use_container_width=True):
            st.switch_page("pages/signup.py")
    st.stop()

col1, col2, col3 = st.columns([2,1,1])
with col1:
    search_term = st.text_input("🔍 Search warranties", "")
with col2:
    category_filter = st.selectbox("Category", ["All"] + CATEGORIES)
with col3:
    date_filter = st.selectbox("Status", ["All", "Expiring Soon"])

warranties = search_warranties(search_term, category_filter, date_filter)

if not warranties:
    st.info("No warranties found matching your criteria.")
else:
    cols = st.columns(3)
    for idx, warranty in enumerate(warranties):
        with cols[idx % 3]:
            with st.container():
                st.write(f"### {warranty[2]}")  
                if warranty[6]:  
                    try:
                        image = Image.open(io.BytesIO(warranty[6]))
                        st.image(image, use_container_width=True)
                    except Exception as e:
                        st.error(f"Error loading image: {str(e)}")
                st.write(f"**Category:** {warranty[3]}")  
                st.write(f"**Expires:** {warranty[5]}")   
                if st.button("View Details", key=f"detail_{warranty[0]}"):
                    st.session_state.selected_warranty = warranty[0]
                    st.switch_page("pages/warranty_details.py")
