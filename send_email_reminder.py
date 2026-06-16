import os
import smtplib
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_email_medicine_reminder(patient_name, patient_email, medicine_name, dosage, reminder_time, schedule_id, scheduled_datetime):
    """
    Sends an HTML-formatted email reminder to a patient using smtplib.
    
    Parameters:
        patient_name (str): Patient's name.
        patient_email (str): Patient's email address.
        medicine_name (str): Name of the medicine.
        dosage (str): Dose amount (e.g. "1 Tablet").
        reminder_time (str): Time of the reminder (e.g. "08:00 AM").
        schedule_id (int): ID of the schedule record.
        scheduled_datetime (str): Datetime formatted string (YYYY-MM-DD HH:MM:SS) representing the scheduled slot.
    """
    # SMTP configuration from environment variables
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    sender_email = os.environ.get('SMTP_USERNAME')
    sender_password = os.environ.get('SMTP_PASSWORD') # Use an App Password for Gmail

    if not sender_email or not sender_password:
        print("[EMAIL ERROR] Missing SMTP_USERNAME or SMTP_PASSWORD environment variables.")
        return False

    # Create the email container
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"⏰ Medicine Reminder: Time to take your {medicine_name}"
    msg['From'] = f"Smart Medicine Reminder <{sender_email}>"
    msg['To'] = patient_email

    # URL-encode parameters for the "Mark as Taken" action link
    # In a standard web application, clicking an email link issues a GET request.
    # The URL points to a landing page or web client endpoint that handles the action.
    encoded_datetime = urllib.parse.quote(scheduled_datetime)
    mark_taken_url = f"http://localhost:5000/mark-taken-web?schedule_id={schedule_id}&scheduled_datetime={encoded_datetime}"

    # Plain-text version of the email (fallback)
    text_content = (
        f"Hi {patient_name},\n\n"
        f"This is a reminder to take your medicine:\n"
        f"- Medicine: {medicine_name}\n"
        f"- Dosage: {dosage}\n"
        f"- Scheduled Time: {reminder_time}\n\n"
        f"To mark this dose as taken, please visit: {mark_taken_url}\n\n"
        f"Stay healthy!"
    )

    # HTML-formatted version of the email (Rich aesthetics)
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                background-color: #f6f9fc;
                color: #333333;
                margin: 0;
                padding: 0;
                -webkit-font-smoothing: antialiased;
            }}
            .container {{
                max-width: 600px;
                margin: 40px auto;
                background-color: #ffffff;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
                overflow: hidden;
                border: 1px solid #eef2f5;
            }}
            .header {{
                background: linear-gradient(135deg, #4F46E5, #7C3AED);
                color: #ffffff;
                padding: 30px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .patient-greeting {{
                font-size: 18px;
                font-weight: bold;
                color: #1F2937;
                margin-bottom: 20px;
            }}
            .medication-card {{
                background-color: #F9FAFB;
                border-left: 4px solid #4F46E5;
                padding: 20px;
                border-radius: 0 8px 8px 0;
                margin-bottom: 30px;
            }}
            .medication-detail {{
                margin: 8px 0;
                font-size: 16px;
            }}
            .label {{
                font-weight: bold;
                color: #4B5563;
                width: 140px;
                display: inline-block;
            }}
            .value {{
                color: #111827;
            }}
            .button-container {{
                text-align: center;
                margin-top: 35px;
            }}
            .btn-taken {{
                background-color: #10B981;
                color: #ffffff !important;
                padding: 14px 28px;
                font-size: 16px;
                font-weight: bold;
                text-decoration: none;
                border-radius: 8px;
                display: inline-block;
                box-shadow: 0 4px 6px rgba(16, 185, 129, 0.2);
                transition: background-color 0.2s;
            }}
            .footer {{
                background-color: #F9FAFB;
                padding: 20px;
                text-align: center;
                font-size: 12px;
                color: #9CA3AF;
                border-top: 1px solid #E5E7EB;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Medicine Reminder</h1>
            </div>
            <div class="content">
                <div class="patient-greeting">Hello {patient_name},</div>
                <p style="font-size: 16px; color: #4B5563; line-height: 1.5;">It is time to take your scheduled dose. Details are provided below:</p>
                
                <div class="medication-card">
                    <div class="medication-detail">
                        <span class="label">💊 Medicine:</span>
                        <span class="value"><strong>{medicine_name}</strong></span>
                    </div>
                    <div class="medication-detail">
                        <span class="label">📋 Dosage:</span>
                        <span class="value">{dosage}</span>
                    </div>
                    <div class="medication-detail">
                        <span class="label">⏰ Scheduled Time:</span>
                        <span class="value">{reminder_time}</span>
                    </div>
                </div>

                <div class="button-container">
                    <a href="{mark_taken_url}" class="btn-taken">Mark as Taken</a>
                </div>
            </div>
            <div class="footer">
                This is an automated reminder from your Smart Medicine Reminder App.<br>
                Please consult your doctor before changing dosages.
            </div>
        </div>
    </body>
    </html>
    """

    # Record MIME representations
    part1 = MIMEText(text_content, 'plain')
    part2 = MIMEText(html_content, 'html')

    msg.attach(part1)
    msg.attach(part2)

    try:
        # Connect to server and send
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Upgrade connection to secure TLS
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, patient_email, msg.as_string())
        server.quit()
        
        print(f"[EMAIL SUCCESS] Reminder email successfully sent to {patient_email}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send email via SMTP: {e}")
        return False

# Example testing block
if __name__ == "__main__":
    # Test values
    p_name = "John Doe"
    p_email = "john.doe@example.com"
    m_name = "Atorvastatin"
    m_dose = "1 Tablet (20mg)"
    m_time = "09:00 PM"
    sched_id = 1
    sched_dt = "2026-06-12 21:00:00"

    print("Attempting to send a mock HTML email reminder...")
    # NOTE: This will fail until valid SMTP credentials are configured in your environment.
    send_email_medicine_reminder(
        patient_name=p_name,
        patient_email=p_email,
        medicine_name=m_name,
        dosage=m_dose,
        reminder_time=m_time,
        schedule_id=sched_id,
        scheduled_datetime=sched_dt
    )
