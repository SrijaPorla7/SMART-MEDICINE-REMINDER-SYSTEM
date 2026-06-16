import os
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

def send_medicine_sms_reminder(patient_name, medicine_name, dosage, reminder_time, to_phone_number):
    """
    Sends an SMS reminder to a patient using the Twilio API.
    
    Parameters:
        patient_name (str): The name of the patient.
        medicine_name (str): The name of the medication.
        dosage (str): The strength/quantity (e.g. "1 Tablet").
        reminder_time (str): The time the dose is scheduled for (e.g. "08:00 AM").
        to_phone_number (str): Recipient's phone number in E.164 format (e.g. "+15551234567").
        
    Returns:
        str: The SID of the successfully sent message if successful, None otherwise.
    """
    # Retrieve credentials from environment variables
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    twilio_number = os.environ.get('TWILIO_PHONE_NUMBER')

    # Basic configuration validation
    if not all([account_sid, auth_token, twilio_number]):
        print("[SMS ERROR] Missing Twilio environment variables configuration.")
        print("Please ensure TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER are set.")
        return None

    # Format the message body
    message_body = (
        f"Hi {patient_name}, this is a friendly reminder to take your medicine:\n"
        f"💊 Medicine: {medicine_name}\n"
        f"📋 Dosage: {dosage}\n"
        f"⏰ Scheduled Time: {reminder_time}\n"
        f"Please mark it as taken once consumed."
    )

    try:
        # Initialize Twilio Client
        client = Client(account_sid, auth_token)

        # Dispatch the SMS
        message = client.messages.create(
            body=message_body,
            from_=twilio_number,
            to=to_phone_number
        )

        print(f"[SMS SUCCESS] Reminder sent to {patient_name} ({to_phone_number}). Message SID: {message.sid}")
        return message.sid

    except TwilioRestException as e:
        print(f"[SMS ERROR] Failed to send SMS via Twilio: {e}")
        return None
    except Exception as e:
        print(f"[SMS ERROR] An unexpected error occurred: {e}")
        return None

# Example testing block
if __name__ == "__main__":
    # Test values (replace with actual numbers for testing)
    test_patient = "John Doe"
    test_medicine = "Lisinopril"
    test_dosage = "1 Tablet (10mg)"
    test_time = "08:00 AM"
    recipient_phone = "+15551234567"  # E.164 format

    print("Attempting to send a mock Twilio SMS Reminder...")
    # NOTE: This will fail until valid credentials and verified phone numbers are configured in env.
    send_medicine_sms_reminder(
        patient_name=test_patient,
        medicine_name=test_medicine,
        dosage=test_dosage,
        reminder_time=test_time,
        to_phone_number=recipient_phone
    )
