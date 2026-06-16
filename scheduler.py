import os
import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
import mysql.connector
from mysql.connector import Error

# Database connection configuration
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'your_password_here')
DB_NAME = os.environ.get('DB_NAME', 'smart_medicine_reminder')

def get_db_connection():
    """Establishes database connection."""
    try:
        return mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
    except Error as e:
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Database connection error: {e}")
        return None

def check_medicine_reminders():
    """
    Every-minute job that:
    1. Checks for doses scheduled *right now*, alerts, and initializes a 'Missed' log.
    2. Checks for doses scheduled *15 minutes ago* that are still marked as 'Missed',
       alerts, and notifies their emergency contact.
    """
    now = datetime.datetime.now()
    current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{current_time_str}] Checking database schedules...")

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor(dictionary=True)

    # ==========================================
    # PART 1: DUE DOSES DETECTION
    # ==========================================
    # Fetch active schedules matching current hour and minute
    due_query = """
        SELECT 
            s.schedule_id,
            s.reminder_time,
            p.first_name,
            p.last_name,
            p.phone,
            m.name AS medicine_name,
            s.dosage,
            s.special_instructions
        FROM schedules s
        INNER JOIN patients p ON s.patient_id = p.patient_id
        INNER JOIN medicines m ON s.medicine_id = m.medicine_id
        WHERE s.is_active = TRUE
          AND s.start_date <= CURDATE()
          AND (s.end_date IS NULL OR s.end_date >= CURDATE())
          AND HOUR(s.reminder_time) = HOUR(NOW())
          AND MINUTE(s.reminder_time) = MINUTE(NOW());
    """

    try:
        cursor.execute(due_query)
        due_doses = cursor.fetchall()
        
        if due_doses:
            print(f"Found {len(due_doses)} dose(s) due at this time.")
            for dose in due_doses:
                patient_name = f"{dose['first_name']} {dose['last_name']}"
                scheduled_time_str = now.strftime("%H:%M")
                
                # Print Due Alert
                print("\n" + "*" * 45)
                print(f"*** [DUE ALERT] Medicine Reminder ***")
                print(f"    Scheduled Time: {scheduled_time_str}")
                print(f"    Patient:        {patient_name} (Phone: {dose['phone']})")
                print(f"    Medicine:       {dose['medicine_name']} ({dose['dosage']})")
                if dose['special_instructions']:
                    print(f"    Instructions:   {dose['special_instructions']}")
                print("*" * 45 + "\n")

                # Initialize a log entry with 'Missed' status.
                # Patient will update this to 'Taken' via the REST API.
                scheduled_datetime = now.replace(second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
                
                insert_log_query = """
                    INSERT INTO dose_logs (schedule_id, scheduled_datetime, status)
                    VALUES (%s, %s, 'Missed')
                    ON DUPLICATE KEY UPDATE status = status; -- Prevent duplicate warnings/logs
                """
                cursor.execute(insert_log_query, (dose['schedule_id'], scheduled_datetime))
            
            conn.commit()

    except Error as e:
        print(f"Error checking due doses: {e}")
        conn.rollback()

    # ==========================================
    # PART 2: MISSED DOSES DETECTION (15 minutes late)
    # ==========================================
    # Check for doses scheduled exactly 15 minutes ago that are still status = 'Missed'
    target_missed_time = now - datetime.timedelta(minutes=15)
    
    # We query logs that fall in a 1-minute window 15 minutes ago
    window_start = target_missed_time.replace(second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    window_end = target_missed_time.replace(second=59, microsecond=999999).strftime("%Y-%m-%d %H:%M:%S")

    missed_query = """
        SELECT 
            dl.log_id,
            dl.scheduled_datetime,
            p.first_name,
            p.last_name,
            p.phone AS patient_phone,
            ec.first_name AS contact_first_name,
            ec.last_name AS contact_last_name,
            ec.phone AS contact_phone,
            m.name AS medicine_name,
            s.dosage
        FROM dose_logs dl
        INNER JOIN schedules s ON dl.schedule_id = s.schedule_id
        INNER JOIN patients p ON s.patient_id = p.patient_id
        INNER JOIN medicines m ON s.medicine_id = m.medicine_id
        LEFT JOIN emergency_contacts ec ON p.patient_id = ec.patient_id
        WHERE dl.status = 'Missed'
          AND dl.scheduled_datetime BETWEEN %s AND %s;
    """

    try:
        cursor.execute(missed_query, (window_start, window_end))
        missed_doses = cursor.fetchall()
        
        if missed_doses:
            for missed in missed_doses:
                patient_name = f"{missed['first_name']} {missed['last_name']}"
                scheduled_time_str = missed['scheduled_datetime'].strftime('%H:%M')
                
                # Print Missed Alert
                print("\n" + "!" * 50)
                print(f"!!! [MISSED DOSE ALERT] Medicine Not Taken !!!")
                print(f"    Scheduled Time: {scheduled_time_str} (15 minutes ago)")
                print(f"    Patient:        {patient_name} (Phone: {missed['patient_phone']})")
                print(f"    Medicine:       {missed['medicine_name']} ({missed['dosage']})")
                
                # Notify Emergency Contact if available
                if missed['contact_phone']:
                    contact_name = f"{missed['contact_first_name']} {missed['contact_last_name']}"
                    print(f"    [NOTIFICATION SENT]")
                    print(f"    Alerting Emergency Contact:")
                    print(f"    Name: {contact_name} | Phone: {missed['contact_phone']}")
                else:
                    print(f"    [WARNING] No emergency contact registered for this patient.")
                print("!" * 50 + "\n")

    except Error as e:
        print(f"Error checking missed doses: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    scheduler = BlockingScheduler()
    
    # Schedule check_medicine_reminders to run every minute
    scheduler.add_job(check_medicine_reminders, 'cron', minute='*')
    
    print("Background Scheduler Started. Press Ctrl+C to exit.")
    print("Checking schedules every minute...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Scheduler stopped.")
