# 🔔 Warranty Management System

A comprehensive web application for managing product warranties built with Streamlit and PostgreSQL.

## 🚀 Project Live Link
<h3> Check out website Live Link </h3>

<h3><a href="https://warranty-tracking-system.streamlit.app/" target="_blank" style="font-size: 24px;">Click Here</a></h3>

<h3> Or </h3>

`https://warranty-tracking-system.streamlit.app/`

## ⭐ Features

- 👤 User Authentication & Authorization
  - Secure signup with email OTP verification
  - Three login methods: password, one-time email code (2FA), and passwordless magic link
  - Forgot password flow with OTP verification (max 3 attempts)
  - Change password from account settings
  - Role-based access (Admin/User)

- 📝 Warranty Management
  - Add warranties with a required warranty card image
  - Attach extra photos and receipts/invoices to each warranty, with individual download/remove
  - Edit and delete existing warranties 
  - Track purchase and expiry dates with date validation
  - Categorize items (Electronics, Appliances, Vehicles, Furniture, Tools, Mobile Devices, Computers, Other)
  - Search by name/description and filter by category or "Expiring Soon" status

- 🔔 Notifications & Reports
  - In-app notification bell showing warranties expiring within 7 days
  - Generate a PDF warranty report with an inline preview before downloading
  - Email yourself a full warranty report (HTML summary + PDF attachment)
  - Daily scheduled emails one day before a warranty expires, plus automatic cleanup of expired items (via a separate GitHub Actions automation repo)

- 👑 Admin Dashboard
  - User management table and system-wide warranty overview
  - Usage statistics: total/new users, total warranties, warranties expiring soon
  - Analytics charts: user roles distribution, warranties by category, top users by item count, category leaders
  - Downloadable and emailable PDF reports for all users and all warranties

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- PostgreSQL (e.g. a Supabase project)
- SMTP server access (for email notifications and OTP/magic-link emails)

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up the PostgreSQL database using the schema in `supabase/script.sql` (creates the `users`, `warranty_items`, `warranty_attachments`, and `magic_link_tokens` tables, and seeds an admin user):
```bash
psql -d your_database -f supabase/script.sql
```
Use `gethash.py` to generate a bcrypt hash for the seeded admin password before inserting it.

3. Configure secrets in `.streamlit/secrets.toml`:
```toml
[postgres]
host = "your-db-host"
port = 5432
database = "db_name"
user = "db_user"
password = "db_password"

[email]
sender = "your-email@gmail.com"
password = "your-app-password"

[app]
base_url = "https://your-deployed-app-url"
```

4. Run the application:
```bash
streamlit run app.py
```

## 💻 Tech Stack

- 🎯 Streamlit - Web framework
- 🐘 PostgreSQL (via psycopg 3) - Database
- 📧 SMTP - Email notifications, OTP, and magic-link delivery
- 📊 Plotly - Data visualization
- 📄 FPDF - PDF generation
- 🖼️ Pillow - Image processing
- 🐼 pandas - Tabular data handling

## 🔒 Security Features

- Password hashing with bcrypt
- Email verification on signup
- Passwordless login via one-time email codes and single-use, time-limited magic links
- OTP-based password recovery with attempt limiting and expiry
- Session management via Streamlit session state
- Role-based access control (Admin/User)

## 🎨 UI Components

- Responsive navigation with role-aware menus
- Interactive charts
- Grid view for warranties
- Image preview and multi-file attachment uploads
- Inline PDF report preview
- Form validation
- Toast notifications

## 🛠️ Scheduled Maintenance Tasks

This project is supported by a scheduled GitHub Actions workflow that performs daily maintenance tasks:

- 📬 Sends reminder emails **one day before** an item's warranty expires
- 🗑️ Automatically deletes items from database whose warranties have already expired

These tasks are managed through a GitHub Actions workflow located in a separate repository:  
👉 [View the automation code here](https://github.com/utsav2110/Warranty_deploy_automation)
