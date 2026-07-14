import streamlit as st
from app import (
    get_conn, Image, io, generate_warranty_pdf, check_expiring_warranties,
    update_warranty_item, delete_warranty_item, validate_dates, CATEGORIES,
    add_attachment, get_attachments, delete_attachment, render_notification_bell,
    render_pdf_preview
)

def get_warranty_by_id(warranty_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM warranty_items 
        WHERE id = %s AND user_id = %s
    """, (warranty_id, st.session_state.get("user_id")))
    warranty = cur.fetchone()
    cur.close()
    conn.close()
    return warranty

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
            st.switch_page("pages/warranties.py")
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

if not st.session_state.get("logged_in"):
    st.warning("Please login to view warranty details")
    st.stop()

warranty_id = st.session_state.get("selected_warranty")
if not warranty_id:
    st.error("No warranty selected")
    st.stop()

warranty = get_warranty_by_id(warranty_id)
if not warranty:
    st.error("Warranty not found")
    st.stop()

st.title(warranty[2])

col1, col2 = st.columns([2,1])
with col1:
    if warranty[6]:
        try:
            image = Image.open(io.BytesIO(warranty[6]))
            st.image(image, use_container_width=True)
        except Exception as e:
            st.error(f"Error loading image: {str(e)}")

with col2:
    st.write("### Details")
    st.write(f"**Category:** {warranty[3]}")
    st.write(f"**Purchase Date:** {warranty[4]}")
    st.write(f"**Warranty End Date:** {warranty[5]}")
    st.write("### Description")
    st.write(warranty[7] or "No description provided")

    edit_col, delete_col = st.columns(2)
    with edit_col:
        if st.button("✏️ Edit", use_container_width=True):
            st.session_state.editing_warranty = True
    with delete_col:
        if st.button("🗑️ Delete", use_container_width=True):
            st.session_state.confirm_delete = True

if st.session_state.get("confirm_delete"):
    st.warning(f"Are you sure you want to delete **{warranty[2]}**? This action cannot be undone.")
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button("Yes, delete it", use_container_width=True, key="confirm_delete_yes"):
            if delete_warranty_item(warranty_id, st.session_state.get("user_id")):
                st.success("Warranty deleted successfully!")
                del st.session_state["confirm_delete"]
                del st.session_state["selected_warranty"]
                st.switch_page("pages/warranties.py")
            else:
                st.error("Failed to delete warranty.")
    with cancel_col:
        if st.button("Cancel", use_container_width=True, key="confirm_delete_cancel"):
            del st.session_state["confirm_delete"]
            st.rerun()

if st.session_state.get("editing_warranty"):
    st.write("### Edit Warranty")
    with st.form("edit_warranty_form"):
        item_name = st.text_input("Item Name*", value=warranty[2])
        category = st.selectbox("Category*", CATEGORIES, index=CATEGORIES.index(warranty[3]) if warranty[3] in CATEGORIES else 0)
        col1, col2 = st.columns(2)
        with col1:
            purchase_date = st.date_input("Purchase Date*", value=warranty[4])
        with col2:
            warranty_end_date = st.date_input("Warranty End Date*", value=warranty[5])
        warranty_image = st.file_uploader("Replace Warranty Card Image (optional)", type=['png', 'jpg', 'jpeg'])
        description = st.text_area("Description (Optional)", value=warranty[7] or "")

        save_col, cancel_col = st.columns(2)
        with save_col:
            submitted = st.form_submit_button("Save Changes", use_container_width=True)
        with cancel_col:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)

        if cancelled:
            del st.session_state["editing_warranty"]
            st.rerun()

        if submitted:
            if not item_name:
                st.error("Please enter item name")
            elif not validate_dates(purchase_date, warranty_end_date):
                st.error("Warranty end date must be after purchase date")
            else:
                image_bytes = warranty_image.read() if warranty_image else None
                if update_warranty_item(
                    warranty_id, st.session_state.get("user_id"),
                    item_name, category, purchase_date,
                    warranty_end_date, description, image_bytes
                ):
                    st.success("Warranty updated successfully!")
                    del st.session_state["editing_warranty"]
                    st.rerun()
                else:
                    st.error("Failed to update warranty.")

st.markdown("---")
st.write("### 📷 Additional Photos")
image_attachments = get_attachments(warranty_id, "image")
if image_attachments:
    img_cols = st.columns(4)
    for idx, attachment in enumerate(image_attachments):
        attachment_id = attachment[0]
        with img_cols[idx % 4]:
            try:
                image = Image.open(io.BytesIO(attachment[5]))
                st.image(image, use_container_width=True, caption=attachment[3])
            except Exception as e:
                st.error(f"Error loading image: {str(e)}")
            if st.button("🗑️ Remove", key=f"del_img_{attachment_id}", use_container_width=True):
                if delete_attachment(attachment_id, warranty_id):
                    st.rerun()
else:
    st.caption("No additional photos uploaded yet.")

with st.expander("➕ Add Photos"):
    new_images = st.file_uploader(
        "Upload additional photos", type=['png', 'jpg', 'jpeg'],
        accept_multiple_files=True, key="new_images_uploader"
    )
    if new_images and st.button("Upload Photos"):
        for img_file in new_images:
            add_attachment(warranty_id, img_file.read(), img_file.name, img_file.type, "image")
        st.success("Photos uploaded successfully!")
        st.rerun()

st.write("### 🧾 Receipts / Invoices")
receipt_attachments = get_attachments(warranty_id, "receipt")
if receipt_attachments:
    for attachment in receipt_attachments:
        attachment_id, file_name, mime_type, file_data = attachment[0], attachment[3], attachment[4], attachment[5]
        r_col1, r_col2, r_col3 = st.columns([3,1,1])
        with r_col1:
            st.write(f"📄 {file_name}")
        with r_col2:
            st.download_button(
                "Download", data=file_data, file_name=file_name,
                mime=mime_type, key=f"download_receipt_{attachment_id}"
            )
        with r_col3:
            if st.button("🗑️ Remove", key=f"del_receipt_{attachment_id}"):
                if delete_attachment(attachment_id, warranty_id):
                    st.rerun()
else:
    st.caption("No receipts or invoices uploaded yet.")

with st.expander("➕ Add Receipt / Invoice"):
    new_receipts = st.file_uploader(
        "Upload receipt or invoice", type=['png', 'jpg', 'jpeg', 'pdf'],
        accept_multiple_files=True, key="new_receipts_uploader"
    )
    if new_receipts and st.button("Upload Receipts"):
        for receipt_file in new_receipts:
            add_attachment(warranty_id, receipt_file.read(), receipt_file.name, receipt_file.type, "receipt")
        st.success("Receipts uploaded successfully!")
        st.rerun()
