# AuraMed | Smart Medicine Reminder System

AuraMed is a complete, database-driven Smart Medicine Reminder System. It assists patients with keeping track of their medication schedules, alerts emergency contacts when critical doses are missed consecutively, predicts high-risk missed dose time periods using historical compliance logs, and offers a dashboard for doctors to monitor patient adherence metrics.

---

## 🛠️ Technology Stack

- **Backend**: Python 3, Flask REST API
- **Database**: MySQL (relational design, indexing, constraints)
- **Background Scheduler**: Python `APScheduler`
- **Integrations**: Twilio API (SMS Alerts), Standard SMTP (`smtplib` for Email Reminders)
- **Frontend**: Vanilla HTML5, CSS3 (Glassmorphic dark-theme, responsive layout), JavaScript (Fetch APIs, Chart.js)

---

## 📂 Project Structure

```text
c:\Users\manxj\OneDrive\Desktop\KS\
├── smart_medicine_reminder.sql   # MySQL database schemas, indexes, and seed datasets
├── app.py                         # Flask REST API server (serves frontend & endpoints)
├── scheduler.py                   # APScheduler daemon (checks reminders & triggers missed events)
├── smart_features.py              # ML/Heuristics module for risk prediction and emergency alerts
├── check_interactions.py          # Local drug-to-drug interaction checker engine
├── send_sms_reminder.py           # Twilio helper script to dispatch SMS notifications
├── send_email_reminder.py         # SMTP helper script to compile & send HTML email reminders
├── drug_interactions.json          # Drug interaction knowledge database (JSON format)
├── HomeScreen.js                  # React Native mobile home screen dashboard component
├── templates/
│   ├── index.html                 # Single-page application UI template
│   └── adherence_report.html      # Weekly adherence report standalone page
└── static/
    ├── css/
    │   └── style.css              # Custom responsive stylesheet (premium glassmorphism)
    └── js/
        └── main.js                # Frontend controllers, event handlers, countdowns & charts
```

---

## 🚀 Setup & Installation

### 1. Database Configuration
1. Log in to your local MySQL instance:
   ```bash
   mysql -u root -p
   ```
2. Import the schema and seed datasets:
   ```sql
   SOURCE c:/Users/manxj/OneDrive/Desktop/KS/smart_medicine_reminder.sql;
   ```

### 2. Install Python Packages
Install the required packages using pip:
   ```bash
   pip install Flask mysql-connector-python apscheduler twilio
   ```

### 3. Set Environment Variables
Set the credentials for MySQL, Twilio, and SMTP.
* **Windows PowerShell**:
  ```powershell
  $env:DB_PASSWORD="your_mysql_password"
  $env:TWILIO_ACCOUNT_SID="your_twilio_sid"
  $env:TWILIO_AUTH_TOKEN="your_twilio_token"
  $env:TWILIO_PHONE_NUMBER="+15017122661"
  $env:SMTP_USERNAME="your_email@gmail.com"
  $env:SMTP_PASSWORD="your_gmail_app_password"
  ```
* **Windows Command Prompt (cmd)**:
  ```cmd
  set DB_PASSWORD=your_mysql_password
  set TWILIO_ACCOUNT_SID=your_twilio_sid
  set TWILIO_AUTH_TOKEN=your_twilio_token
  set TWILIO_PHONE_NUMBER=+15017122661
  set SMTP_USERNAME=your_email@gmail.com
  set SMTP_PASSWORD=your_gmail_app_password
  ```

---

## 🏃 Running the Application

AuraMed consists of two core components running concurrently:

1. **Flask API Server** (Serves the dashboard and endpoints):
   ```bash
   python app.py
   ```
   *Open your browser and navigate to `http://localhost:5000`.*

2. **Background Scheduler Daemon** (Watches time, flags missed doses, and sends alerts):
   ```bash
   python scheduler.py
   ```

---

## 📋 API Endpoints Documentation

### 1. Patient Registration
- **Route**: `POST /register`
- **Payload**:
  ```json
  {
    "first_name": "John",
    "last_name": "Doe",
    "date_of_birth": "1975-04-12",
    "gender": "Male",
    "phone": "+1-555-1234",
    "email": "john.doe@email.com",
    "password": "password123",
    "address": "123 Elm St",
    "primary_doctor_id": 1
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "message": "Patient registered successfully",
    "data": { "patient_id": 1, "first_name": "John", "email": "john.doe@email.com" }
  }
  ```

### 2. Patient Login
- **Route**: `POST /login`
- **Payload**: `{"email": "john.doe@email.com", "password": "password123"}`
- **Response**: Returns patient details.

### 3. Add & Schedule Medicine
- **Route**: `POST /add-medicine`
- **Payload**:
  ```json
  {
    "patient_id": 1,
    "name": "Aspirin",
    "form": "Tablet",
    "strength": "81mg",
    "dosage": "1 Tablet",
    "frequency": "Daily",
    "reminder_time": "08:00:00",
    "start_date": "2026-06-12"
  }
  ```
- **Response**: Returns `schedule_id` and `medicine_id`.

### 4. Fetch Schedules
- **Route**: `GET /medicines/<int:user_id>`
- **Response**: Array of all active medication schedules.

### 5. Mark Dose as Taken
- **Route**: `POST /mark-taken`
- **Payload**:
  ```json
  {
    "schedule_id": 1,
    "scheduled_datetime": "2026-06-12 08:00:00",
    "status": "Taken"
  }
  ```
- **Response**: `{"success": true, "message": "Dose marked as 'Taken' successfully."}`

### 6. Adherence Report
- **Route**: `GET /adherence-report/<int:user_id>`
- **Response**: Returns stats count (Taken, Missed, Skipped, Delayed), adherence percentage, and past 20 history log details.

### 7. AI Risk Window Prediction
- **Route**: `GET /prediction/<int:user_id>`
- **Response**: Analyzes history to predict the most high-risk 2-hour window where the user has the highest miss rate.

### 8. Doctor Portal Patient List
- **Route**: `GET /doctor/patients`
- **Response**: Returns a table structure array of all patients, their drugs, and compliance ratios.

### 9. Weekly Adherence Report Page
- **Route**: `GET /adherence-report-page`
- **Response**: Renders a standalone dashboard containing the Chart.js visual compliance analytics mapping taken vs missed doses for the last 7 days.

