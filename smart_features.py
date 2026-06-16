import os
import datetime
import mysql.connector
from mysql.connector import Error
from send_sms_reminder import send_medicine_sms_reminder

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'your_password_here')
DB_NAME = os.environ.get('DB_NAME', 'smart_medicine_reminder')

def get_db_connection():
    try:
        return mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
    except Error as e:
        print(f"Database error in smart_features: {e}")
        return None

def predict_high_risk_missed_slot(patient_id):
    """
    Analyzes a patient's historical dose logs to determine which 2-hour
    window has the highest failure rate (Missed / Total Doses Scheduled).
    """
    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}

    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT 
            HOUR(dl.scheduled_datetime) AS hour_of_day,
            dl.status
        FROM dose_logs dl
        INNER JOIN schedules s ON dl.schedule_id = s.schedule_id
        WHERE s.patient_id = %s
    """
    try:
        cursor.execute(query, (patient_id,))
        logs = cursor.fetchall()
        
        if not logs:
            return {
                "high_risk_window": "Insufficient Data",
                "miss_rate": 0.0,
                "total_doses": 0,
                "message": "No medication log history found for this patient."
            }

        # Initialize slots: each slot represents a 2-hour window (e.g. 0 represents 00:00-02:00, 1 represents 02:00-04:00, etc.)
        # We will collect total doses and missed doses per slot
        slots = {i: {"total": 0, "missed": 0} for i in range(12)}
        
        for log in logs:
            hour = log['hour_of_day']
            status = log['status']
            slot_id = hour // 2
            
            slots[slot_id]["total"] += 1
            if status in ['Missed', 'Skipped']:
                slots[slot_id]["missed"] += 1

        # Calculate miss rates and find the highest
        max_rate = -1.0
        worst_slot = None
        total_doses_in_worst = 0
        missed_doses_in_worst = 0

        for slot_id, stats in slots.items():
            if stats["total"] > 0:
                rate = stats["missed"] / stats["total"]
                # Prioritize windows that actually have failures
                if rate > max_rate and stats["missed"] > 0:
                    max_rate = rate
                    worst_slot = slot_id
                    total_doses_in_worst = stats["total"]
                    missed_doses_in_worst = stats["missed"]

        if worst_slot is None:
            return {
                "high_risk_window": "Low Risk",
                "miss_rate": 0.0,
                "total_doses": len(logs),
                "message": "Excellent adherence! No missed dose patterns detected."
            }

        start_hour = worst_slot * 2
        end_hour = start_hour + 2
        window_label = f"{start_hour:02d}:00 - {end_hour:02d}:00"
        
        return {
            "high_risk_window": window_label,
            "miss_rate_percentage": round(max_rate * 100, 1),
            "missed_doses": missed_doses_in_worst,
            "total_scheduled_doses_in_window": total_doses_in_worst,
            "message": f"Patient is at highest risk between {window_label} with a {round(max_rate * 100, 1)}% miss rate."
        }

    except Error as e:
        return {"error": f"Database query failed: {e}"}
    finally:
        cursor.close()
        conn.close()

def check_consecutive_missed_critical_doses(patient_id, threshold=3):
    """
    Checks if the patient has missed more than 'threshold' consecutive doses.
    If yes, triggers an emergency Twilio SMS alert to the emergency contact.
    """
    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}

    cursor = conn.cursor(dictionary=True)
    
    # 1. Fetch patient's active schedules
    schedules_query = """
        SELECT schedule_id, medicine_id 
        FROM schedules 
        WHERE patient_id = %s AND is_active = TRUE
    """
    
    # 2. Get emergency contact information
    contact_query = """
        SELECT 
            p.first_name AS patient_first, p.last_name AS patient_last,
            ec.first_name AS contact_first, ec.last_name AS contact_last,
            ec.phone AS contact_phone, m.name AS medicine_name, s.dosage
        FROM emergency_contacts ec
        INNER JOIN patients p ON ec.patient_id = p.patient_id
        INNER JOIN schedules s ON s.patient_id = p.patient_id
        INNER JOIN medicines m ON s.medicine_id = m.medicine_id
        WHERE p.patient_id = %s AND s.schedule_id = %s
        LIMIT 1
    """

    try:
        cursor.execute(schedules_query, (patient_id,))
        schedules = cursor.fetchall()
        
        triggered_alerts = []

        for sched in schedules:
            schedule_id = sched['schedule_id']
            
            # Fetch last N logs for this schedule
            logs_query = """
                SELECT status, scheduled_datetime 
                FROM dose_logs 
                WHERE schedule_id = %s 
                ORDER BY scheduled_datetime DESC 
                LIMIT %s
            """
            cursor.execute(logs_query, (schedule_id, threshold))
            recent_logs = cursor.fetchall()
            
            # Check if all recent N logs are 'Missed'
            if len(recent_logs) >= threshold and all(log['status'] == 'Missed' for log in recent_logs):
                # Trigger alert! Fetch details
                cursor.execute(contact_query, (patient_id, schedule_id))
                details = cursor.fetchone()
                
                if details and details['contact_phone']:
                    p_name = f"{details['patient_first']} {details['patient_last']}"
                    c_name = f"{details['contact_first']} {details['contact_last']}"
                    med_name = details['medicine_name']
                    dose = details['dosage']
                    
                    # Construct Twilio SMS body
                    sms_body = (
                        f"⚠️ EMERGENCY ALERT: {p_name} has missed {threshold} consecutive doses of "
                        f"critical medicine: {med_name} ({dose}). "
                        f"Please check in immediately."
                    )
                    
                    # Dispatch viaTwilio helper
                    sid = send_medicine_sms_reminder(
                        patient_name=p_name,
                        medicine_name=med_name,
                        dosage=dose,
                        reminder_time=f"last {threshold} doses",
                        to_phone_number=details['contact_phone']
                    )
                    
                    triggered_alerts.append({
                        "schedule_id": schedule_id,
                        "medicine_name": med_name,
                        "consecutive_misses": len(recent_logs),
                        "emergency_contact": c_name,
                        "phone": details['contact_phone'],
                        "alert_sid": sid
                    })
        
        return {
            "success": True,
            "alerts_triggered": triggered_alerts,
            "message": f"Checked {len(schedules)} schedules. Triggered {len(triggered_alerts)} emergency alert(s)."
        }

    except Error as e:
        return {"error": f"Database query failed: {e}"}
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    # Test script run
    print("Testing Smart Features Module...")
    # Test high-risk prediction on Patient 1 (John Doe)
    prediction = predict_high_risk_missed_slot(patient_id=1)
    print("Prediction Result:", prediction)
    
    # Test emergency alerts check on Patient 1
    alert_check = check_consecutive_missed_critical_doses(patient_id=1, threshold=1) # using threshold 1 to test
    print("Alert Check Result:", alert_check)
