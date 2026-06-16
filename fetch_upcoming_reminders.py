import os
import datetime
import mysql.connector
from mysql.connector import Error

def get_db_connection():
    """Establishes connection to the MySQL database."""
    try:
        # Default connection parameters - edit these or set environment variables
        connection = mysql.connector.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            user=os.environ.get('DB_USER', 'root'),
            password=os.environ.get('DB_PASSWORD', 'your_password_here'),
            database=os.environ.get('DB_NAME', 'smart_medicine_reminder')
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL database: {e}")
        return None

def fetch_due_medicines(minutes_window=30):
    """
    Fetches all active medicine schedules due within the specified minutes window.
    Handles the midnight rollover boundary condition.
    """
    connection = get_db_connection()
    if not connection:
        return

    cursor = connection.cursor(dictionary=True)
    
    # SQL query that calculates the time window.
    # It accounts for cases where the window crosses midnight (e.g. current time 23:45, window ends at 00:15).
    query = """
        SELECT 
            s.schedule_id,
            p.patient_id,
            CONCAT(p.first_name, ' ', p.last_name) AS patient_name,
            p.phone AS patient_phone,
            m.name AS medicine_name,
            s.dosage,
            s.reminder_time,
            s.special_instructions
        FROM schedules s
        INNER JOIN patients p ON s.patient_id = p.patient_id
        INNER JOIN medicines m ON s.medicine_id = m.medicine_id
        WHERE s.is_active = TRUE
          AND s.start_date <= CURDATE()
          AND (s.end_date IS NULL OR s.end_date >= CURDATE())
          AND (
              -- Case 1: Simple range within the same day
              (
                  s.reminder_time BETWEEN CURTIME() AND ADDTIME(CURTIME(), %s)
                  AND ADDTIME(CURTIME(), %s) < '24:00:00'
              )
              OR
              -- Case 2: Rollover past midnight
              (
                  ADDTIME(CURTIME(), %s) >= '24:00:00'
                  AND (
                      s.reminder_time >= CURTIME() 
                      OR s.reminder_time <= TIME(ADDTIME(CURTIME(), %s))
                  )
              )
          )
        ORDER BY s.reminder_time ASC;
    """

    time_str = f"00:{minutes_window:02d}:00"
    params = (time_str, time_str, time_str, time_str)

    try:
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"--- Fetching upcoming reminders (Time Now: {current_time}, Window: Next {minutes_window} mins) ---")
        
        if not results:
            print("No medicines are due in the next 30 minutes.")
        else:
            for row in results:
                # Convert timedelta representation of TIME to a formatted string
                reminder_time = str(row['reminder_time'])
                
                print(f"\n[REMINDER] Schedule ID: {row['schedule_id']}")
                print(f"  Patient:  {row['patient_name']} (Phone: {row['patient_phone']})")
                print(f"  Medicine: {row['medicine_name']} ({row['dosage']})")
                print(f"  Due Time: {reminder_time}")
                if row['special_instructions']:
                    print(f"  Instructions: {row['special_instructions']}")
                    
    except Error as e:
        print(f"Failed to execute query: {e}")
    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    fetch_due_medicines(minutes_window=30)
