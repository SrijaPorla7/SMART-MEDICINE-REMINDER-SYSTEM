import os
import datetime
from flask import Flask, request, jsonify, render_template, redirect
from mysql.connector import pooling, Error
from werkzeug.security import generate_password_hash, check_password_hash
from smart_features import predict_high_risk_missed_slot

app = Flask(__name__)

# Configure JSON formatting
app.config['JSON_SORT_KEYS'] = False

# Initialize MySQL connection pool
# These parameters can be overridden using environment variables
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'your_password_here')
DB_NAME = os.environ.get('DB_NAME', 'smart_medicine_reminder')

try:
    db_pool = pooling.MySQLConnectionPool(
        pool_name="medpool",
        pool_size=10,
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    print("MySQL Connection Pool initialized successfully.")
except Error as e:
    print(f"Error creating MySQL connection pool: {e}")
    db_pool = None

def get_db_connection():
    """Gets a connection from the connection pool."""
    if db_pool:
        return db_pool.get_connection()
    raise Exception("Database connection pool is not initialized.")


# Helper to convert timedelta (returned by MySQL TIME) to "HH:MM:SS" string
def format_time(t):
    if isinstance(t, datetime.timedelta):
        hours, remainder = divmod(t.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    elif isinstance(t, datetime.time):
        return t.strftime("%H:%M:%S")
    return str(t)

# Helper to convert datetime and date types for JSON serialization
def serialize_db_row(row):
    for key, value in row.items():
        if isinstance(value, (datetime.datetime, datetime.date)):
            row[key] = value.isoformat()
        elif isinstance(value, datetime.timedelta):
            row[key] = format_time(value)
    return row


# ==========================================
# 1. POST /register
# ==========================================
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    
    # Required field validation
    required_fields = ['first_name', 'last_name', 'date_of_birth', 'gender', 'phone', 'email', 'password']
    missing_fields = [f for f in required_fields if f not in data or not str(data[f]).strip()]
    if missing_fields:
        return jsonify({
            "success": False,
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }), 400

    first_name = data['first_name'].strip()
    last_name = data['last_name'].strip()
    date_of_birth = data['date_of_birth'].strip()
    gender = data['gender'].strip()
    phone = data['phone'].strip()
    email = data['email'].strip().lower()
    password = data['password']
    address = data.get('address', '').strip()
    primary_doctor_id = data.get('primary_doctor_id')

    if gender not in ['Male', 'Female', 'Other']:
        return jsonify({"success": False, "message": "Gender must be 'Male', 'Female', or 'Other'"}), 400

    # Hash the password
    password_hash = generate_password_hash(password)

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if email already exists
        cursor.execute("SELECT patient_id FROM patients WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Email is already registered"}), 409

        # Verify doctor exists if primary_doctor_id is supplied
        if primary_doctor_id:
            cursor.execute("SELECT doctor_id FROM doctors WHERE doctor_id = %s", (primary_doctor_id,))
            if not cursor.fetchone():
                return jsonify({"success": False, "message": f"Doctor ID {primary_doctor_id} not found"}), 404

        # Insert new patient
        insert_query = """
            INSERT INTO patients (first_name, last_name, date_of_birth, gender, phone, email, password_hash, address, primary_doctor_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (
            first_name, last_name, date_of_birth, gender, phone, email, password_hash, address, primary_doctor_id
        ))
        conn.commit()
        
        patient_id = cursor.lastrowid
        return jsonify({
            "success": True,
            "message": "Patient registered successfully",
            "data": {
                "patient_id": patient_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": email
            }
        }), 201

    except Error as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": f"Database error: {e}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==========================================
# 2. POST /login
# ==========================================
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password')

    if not email or not password:
        return jsonify({"success": False, "message": "Email and password are required"}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Retrieve user record
        cursor.execute("SELECT * FROM patients WHERE email = %s", (email,))
        patient = cursor.fetchone()

        if not patient or not check_password_hash(patient['password_hash'], password):
            return jsonify({"success": False, "message": "Invalid email or password"}), 401

        return jsonify({
            "success": True,
            "message": "Login successful",
            "data": {
                "patient_id": patient['patient_id'],
                "first_name": patient['first_name'],
                "last_name": patient['last_name'],
                "email": patient['email']
            }
        }), 200

    except Error as e:
        return jsonify({"success": False, "message": f"Database error: {e}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==========================================
# 3. POST /add-medicine
# ==========================================
@app.route('/add-medicine', methods=['POST'])
def add_medicine():
    """
    Registers a medicine in the catalog (if not already existing) AND 
    optionally creates a dosage schedule for a specific patient.
    """
    data = request.get_json() or {}
    
    # Required Medicine Parameters
    required_med_fields = ['name', 'form', 'strength']
    missing_med_fields = [f for f in required_med_fields if f not in data or not str(data[f]).strip()]
    if missing_med_fields:
        return jsonify({
            "success": False,
            "message": f"Missing medicine catalog fields: {', '.join(missing_med_fields)}"
        }), 400

    name = data['name'].strip()
    form = data['form'].strip()
    strength = data['strength'].strip()
    manufacturer = data.get('manufacturer', '').strip() or None
    description = data.get('description', '').strip() or None

    if form not in ['Tablet', 'Capsule', 'Syrup', 'Injection', 'Inhaler', 'Drops', 'Ointment', 'Other']:
        return jsonify({"success": False, "message": "Invalid form value type"}), 400

    # Check for schedule parameters
    patient_id = data.get('patient_id')
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Add or locate the medicine in catalog
        cursor.execute(
            "SELECT medicine_id FROM medicines WHERE name = %s AND form = %s AND strength = %s",
            (name, form, strength)
        )
        existing_med = cursor.fetchone()
        
        if existing_med:
            medicine_id = existing_med['medicine_id']
        else:
            insert_med_query = """
                INSERT INTO medicines (name, form, strength, manufacturer, description)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(insert_med_query, (name, form, strength, manufacturer, description))
            medicine_id = cursor.lastrowid

        # 2. Optionally create the reminder schedule if patient_id is present
        schedule_id = None
        if patient_id:
            # Check if patient exists
            cursor.execute("SELECT patient_id FROM patients WHERE patient_id = %s", (patient_id,))
            if not cursor.fetchone():
                return jsonify({"success": False, "message": f"Patient ID {patient_id} does not exist."}), 404

            # Required Schedule Parameters
            required_sched_fields = ['dosage', 'frequency', 'reminder_time']
            missing_sched_fields = [f for f in required_sched_fields if f not in data or not str(data[f]).strip()]
            if missing_sched_fields:
                return jsonify({
                    "success": False,
                    "message": f"Missing reminder schedule fields: {', '.join(missing_sched_fields)}"
                }), 400

            dosage = data['dosage'].strip()
            frequency = data['frequency'].strip()
            reminder_time = data['reminder_time'].strip() # Format: HH:MM:SS
            start_date = data.get('start_date', datetime.date.today().isoformat()).strip()
            end_date = data.get('end_date')
            if end_date: end_date = end_date.strip()
            special_instructions = data.get('special_instructions', '').strip() or None

            if frequency not in ['Daily', 'Alternate Days', 'Weekly', 'As Needed']:
                return jsonify({"success": False, "message": "Frequency must be Daily, Alternate Days, Weekly, or As Needed"}), 400

            insert_schedule_query = """
                INSERT INTO schedules (patient_id, medicine_id, dosage, frequency, reminder_time, start_date, end_date, special_instructions)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_schedule_query, (
                patient_id, medicine_id, dosage, frequency, reminder_time, start_date, end_date, special_instructions
            ))
            schedule_id = cursor.lastrowid

        conn.commit()
        
        response_data = {
            "medicine_id": medicine_id,
            "name": name,
            "form": form,
            "strength": strength
        }
        if schedule_id:
            response_data["schedule_id"] = schedule_id
            message = "Medicine added and scheduled successfully"
        else:
            message = "Medicine registered in catalog successfully"

        return jsonify({
            "success": True,
            "message": message,
            "data": response_data
        }), 201

    except Error as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": f"Database error: {e}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==========================================
# 4. GET /medicines/:user_id
# ==========================================
@app.route('/medicines/<int:user_id>', methods=['GET'])
def get_user_medicines(user_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if patient exists
        cursor.execute("SELECT patient_id FROM patients WHERE patient_id = %s", (user_id,))
        if not cursor.fetchone():
            return jsonify({"success": False, "message": "Patient not found"}), 404

        # Query active & inactive schedules for the user
        query = """
            SELECT 
                s.schedule_id,
                m.medicine_id,
                m.name AS medicine_name,
                m.form,
                m.strength,
                m.manufacturer,
                m.description AS medicine_description,
                s.dosage,
                s.frequency,
                s.reminder_time,
                s.start_date,
                s.end_date,
                s.special_instructions,
                s.is_active
            FROM schedules s
            INNER JOIN medicines m ON s.medicine_id = m.medicine_id
            WHERE s.patient_id = %s
            ORDER BY s.is_active DESC, s.reminder_time ASC;
        """
        cursor.execute(query, (user_id,))
        schedules = cursor.fetchall()

        # Format and serialize types
        formatted_schedules = [serialize_db_row(row) for row in schedules]

        return jsonify({
            "success": True,
            "count": len(formatted_schedules),
            "data": formatted_schedules
        }), 200

    except Error as e:
        return jsonify({"success": False, "message": f"Database error: {e}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==========================================
# 5. POST /mark-taken
# ==========================================
@app.route('/mark-taken', methods=['POST'])
def mark_taken():
    data = request.get_json() or {}
    
    required_fields = ['schedule_id', 'scheduled_datetime']
    missing_fields = [f for f in required_fields if f not in data or not str(data[f]).strip()]
    if missing_fields:
        return jsonify({
            "success": False,
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }), 400

    schedule_id = data['schedule_id']
    scheduled_datetime = data['scheduled_datetime'].strip() # format: YYYY-MM-DD HH:MM:SS
    status = data.get('status', 'Taken').strip() # Taken, Missed, Skipped, Delayed
    notes = data.get('notes', '').strip() or None
    
    if status not in ['Taken', 'Missed', 'Skipped', 'Delayed']:
        return jsonify({"success": False, "message": "Status must be Taken, Missed, Skipped, or Delayed"}), 400

    # Determine taken_datetime
    taken_datetime = None
    if status in ['Taken', 'Delayed']:
        # If user supplies taken_datetime, use it. Otherwise, use current timestamp.
        taken_datetime = data.get('taken_datetime', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")).strip()

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify schedule exists
        cursor.execute("SELECT schedule_id FROM schedules WHERE schedule_id = %s", (schedule_id,))
        if not cursor.fetchone():
            return jsonify({"success": False, "message": f"Schedule ID {schedule_id} does not exist"}), 404

        # Upsert log entry (using unique constraint uq_schedule_time)
        upsert_query = """
            INSERT INTO dose_logs (schedule_id, scheduled_datetime, status, taken_datetime, notes)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                status = VALUES(status),
                taken_datetime = VALUES(taken_datetime),
                notes = VALUES(notes)
        """
        cursor.execute(upsert_query, (schedule_id, scheduled_datetime, status, taken_datetime, notes))
        conn.commit()

        return jsonify({
            "success": True,
            "message": f"Dose marked as '{status}' successfully."
        }), 200

    except Error as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": f"Database error: {e}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==========================================
# 6. GET /adherence-report/:user_id
# ==========================================
@app.route('/adherence-report/<int:user_id>', methods=['GET'])
def get_adherence_report(user_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        
        # 1. Verify Patient and get Info
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT first_name, last_name, email FROM patients WHERE patient_id = %s", (user_id,))
        patient = cursor.fetchone()
        if not patient:
            return jsonify({"success": False, "message": "Patient not found"}), 404

        # 2. Get status counts for the patient
        counts_query = """
            SELECT 
                dl.status,
                COUNT(*) as count
            FROM dose_logs dl
            INNER JOIN schedules s ON dl.schedule_id = s.schedule_id
            WHERE s.patient_id = %s
            GROUP BY dl.status;
        """
        cursor.execute(counts_query, (user_id,))
        status_counts = cursor.fetchall()

        # Initialize counts
        summary = {
            "Taken": 0,
            "Missed": 0,
            "Skipped": 0,
            "Delayed": 0
        }
        total_doses = 0
        for row in status_counts:
            status = row['status']
            count = row['count']
            summary[status] = count
            total_doses += count

        # Calculate adherence rate: (Taken + Delayed) / Total
        adherence_rate = 0.0
        if total_doses > 0:
            taken_or_delayed = summary['Taken'] + summary['Delayed']
            adherence_rate = round((taken_or_delayed / total_doses) * 100, 2)

        # 3. Fetch recent dose logs (limit 20)
        logs_query = """
            SELECT 
                dl.log_id,
                m.name AS medicine_name,
                m.form,
                s.dosage,
                dl.scheduled_datetime,
                dl.status,
                dl.taken_datetime,
                dl.notes
            FROM dose_logs dl
            INNER JOIN schedules s ON dl.schedule_id = s.schedule_id
            INNER JOIN medicines m ON s.medicine_id = m.medicine_id
            WHERE s.patient_id = %s
            ORDER BY dl.scheduled_datetime DESC
            LIMIT 20;
        """
        cursor.execute(logs_query, (user_id,))
        recent_logs = cursor.fetchall()
        
        # Format datetimes
        formatted_logs = [serialize_db_row(row) for row in recent_logs]

        return jsonify({
            "success": True,
            "data": {
                "patient": {
                    "patient_id": user_id,
                    "name": f"{patient['first_name']} {patient['last_name']}",
                    "email": patient['email']
                },
                "adherence_summary": {
                    "total_logged_doses": total_doses,
                    "details": summary,
                    "adherence_rate_percentage": adherence_rate
                },
                "recent_logs": formatted_logs
            }
        }), 200

    except Error as e:
        return jsonify({"success": False, "message": f"Database error: {e}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==========================================
# 7. GET / (Frontend Dashboard)
# ==========================================
@app.route('/')
def home():
    return render_template('index.html')


# ==========================================
# 8. GET /mark-taken-web (Email Action Handler)
# ==========================================
@app.route('/mark-taken-web', methods=['GET'])
def mark_taken_web():
    import urllib.parse
    schedule_id = request.args.get('schedule_id')
    scheduled_datetime = request.args.get('scheduled_datetime')
    
    if not schedule_id or not scheduled_datetime:
        return "Missing parameters", 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify schedule exists and get medicine name
        cursor.execute("""
            SELECT m.name 
            FROM schedules s
            INNER JOIN medicines m ON s.medicine_id = m.medicine_id
            WHERE s.schedule_id = %s
        """, (schedule_id,))
        row = cursor.fetchone()
        if not row:
            return "Schedule not found", 404
        med_name = row[0]

        # Upsert log entry (marked as Taken)
        upsert_query = """
            INSERT INTO dose_logs (schedule_id, scheduled_datetime, status, taken_datetime)
            VALUES (%s, %s, 'Taken', NOW())
            ON DUPLICATE KEY UPDATE 
                status = 'Taken',
                taken_datetime = NOW()
        """
        cursor.execute(upsert_query, (schedule_id, scheduled_datetime))
        conn.commit()

        # Redirect user back to home page with toast notification parameters
        return redirect(f"/?action=marked_taken&med_name={urllib.parse.quote(med_name)}")

    except Error as e:
        if conn: conn.rollback()
        return f"Database error: {e}", 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==========================================
# 9. GET /prediction/:user_id (AI Analytics)
# ==========================================
@app.route('/prediction/<int:user_id>', methods=['GET'])
def get_user_prediction(user_id):
    prediction = predict_high_risk_missed_slot(user_id)
    if "error" in prediction:
        return jsonify({"success": False, "message": prediction["error"]}), 500
    return jsonify({"success": True, "data": prediction}), 200


# ==========================================
# 10. GET /doctor/patients (Doctor Portal Views)
# ==========================================
@app.route('/doctor/patients', methods=['GET'])
def get_doctor_patients():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT 
                p.patient_id,
                CONCAT(p.first_name, ' ', p.last_name) AS name,
                p.email,
                p.phone,
                GROUP_CONCAT(DISTINCT m.name SEPARATOR ', ') AS medicines,
                COUNT(dl.log_id) AS total_logged,
                SUM(CASE WHEN dl.status IN ('Taken', 'Delayed') THEN 1 ELSE 0 END) AS taken_logged
            FROM patients p
            LEFT JOIN schedules s ON p.patient_id = s.patient_id AND s.is_active = TRUE
            LEFT JOIN medicines m ON s.medicine_id = m.medicine_id
            LEFT JOIN dose_logs dl ON s.schedule_id = dl.schedule_id
            GROUP BY p.patient_id;
        """
        cursor.execute(query)
        patients_data = cursor.fetchall()

        formatted_patients = []
        for row in patients_data:
            total = row['total_logged']
            taken = row['taken_logged'] if row['taken_logged'] else 0
            adherence = round((taken / total) * 100, 1) if total > 0 else 100.0
            
            formatted_patients.append({
                "patient_id": row['patient_id'],
                "name": row['name'],
                "email": row['email'],
                "phone": row['phone'],
                "medicines": row['medicines'] if row['medicines'] else "No Active Medications",
                "adherence_percentage": adherence
            })

        return jsonify({
            "success": True,
            "count": len(formatted_patients),
            "data": formatted_patients
        }), 200

    except Error as e:
        return jsonify({"success": False, "message": f"Database error: {e}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==========================================
# 11. GET /adherence-report-page (Adherence Report Page)
# ==========================================
@app.route('/adherence-report-page')
def adherence_report_page():
    return render_template('adherence_report.html')


# ==========================================
# 12. GET /doctor-portal (Doctor Portal Page)
# ==========================================
@app.route('/doctor-portal')
def doctor_portal_page():
    return render_template('doctor_portal.html')


if __name__ == '__main__':
    # Running locally on port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)

