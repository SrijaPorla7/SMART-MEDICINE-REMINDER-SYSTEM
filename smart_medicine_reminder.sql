-- Smart Medicine Reminder System - MySQL Database Schema & Sample Data
-- Created: 2026-06-12

CREATE DATABASE IF NOT EXISTS smart_medicine_reminder;
USE smart_medicine_reminder;

-- ==========================================
-- 1. DOCTORS TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS doctors (
    doctor_id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    specialization VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    clinic_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ==========================================
-- 2. PATIENTS TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS patients (
    patient_id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    date_of_birth DATE NOT NULL,
    gender ENUM('Male', 'Female', 'Other') NOT NULL,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    address TEXT,
    primary_doctor_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (primary_doctor_id) 
        REFERENCES doctors(doctor_id) 
        ON DELETE SET NULL 
        ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ==========================================
-- 3. EMERGENCY CONTACTS TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS emergency_contacts (
    contact_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    relationship VARCHAR(50) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) 
        REFERENCES patients(patient_id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ==========================================
-- 4. MEDICINES TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS medicines (
    medicine_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    form ENUM('Tablet', 'Capsule', 'Syrup', 'Injection', 'Inhaler', 'Drops', 'Ointment', 'Other') NOT NULL,
    strength VARCHAR(50) NOT NULL, -- e.g., "500mg", "10ml", "100mcg"
    manufacturer VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ==========================================
-- 5. SCHEDULES TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS schedules (
    schedule_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    medicine_id INT NOT NULL,
    dosage VARCHAR(50) NOT NULL, -- e.g., "1 Tablet", "5ml"
    frequency ENUM('Daily', 'Alternate Days', 'Weekly', 'As Needed') NOT NULL,
    reminder_time TIME NOT NULL, -- The specific time of day for the dose
    start_date DATE NOT NULL,
    end_date DATE, -- NULL if it's an ongoing long-term prescription
    special_instructions TEXT, -- e.g., "Take after meals", "Do not take with milk"
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) 
        REFERENCES patients(patient_id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE,
    FOREIGN KEY (medicine_id) 
        REFERENCES medicines(medicine_id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ==========================================
-- 6. DOSE LOGS TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS dose_logs (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    schedule_id INT NOT NULL,
    scheduled_datetime DATETIME NOT NULL,
    status ENUM('Taken', 'Missed', 'Skipped', 'Delayed') NOT NULL DEFAULT 'Missed',
    taken_datetime DATETIME, -- The actual time the patient marked it as taken
    notes TEXT, -- Patient comments (e.g., "Felt dizzy after taking")
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (schedule_id) 
        REFERENCES schedules(schedule_id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE,
    UNIQUE KEY uq_schedule_time (schedule_id, scheduled_datetime)
) ENGINE=InnoDB;

-- ==========================================
-- INDEXES FOR PERFORMANCE OPTIMIZATION
-- ==========================================
CREATE INDEX idx_patients_doctor ON patients(primary_doctor_id);
CREATE INDEX idx_emergency_contacts_patient ON emergency_contacts(patient_id);
CREATE INDEX idx_schedules_patient ON schedules(patient_id);
CREATE INDEX idx_schedules_medicine ON schedules(medicine_id);
CREATE INDEX idx_dose_logs_schedule ON dose_logs(schedule_id);
CREATE INDEX idx_dose_logs_status_time ON dose_logs(scheduled_datetime, status);


-- ==========================================
-- SAMPLE DATA INSERTS
-- ==========================================

-- 1. Insert Doctors
INSERT INTO doctors (first_name, last_name, specialization, phone, email, clinic_address) VALUES
('Sarah', 'Conner', 'Cardiology', '+1-555-0199', 'dr.conner@healthcenter.com', 'Suite 402, Heart & Vascular Institute, Metro Hospital'),
('James', 'Smith', 'Endocrinology', '+1-555-0245', 'dr.smith@healthcenter.com', 'Room 12B, Endocrinology Wing, Metro Hospital'),
('Elena', 'Vasiliev', 'General Medicine', '+1-555-0312', 'dr.vasiliev@healthcenter.com', '104 Wellness Blvd, Care Clinic');

-- 2. Insert Patients (default password for all is 'password123')
INSERT INTO patients (first_name, last_name, date_of_birth, gender, phone, email, password_hash, address, primary_doctor_id) VALUES
('John', 'Doe', '1975-04-12', 'Male', '+1-555-1234', 'john.doe@email.com', 'scrypt:32768:8:1$q8fJcO5zG7aK2sP1$a1d17d591871a2a4bc03d157a972cbe0a3a71b69a25b1b4b9b9a6a8a0a9a1a9a', '123 Elm St, Springfield', 1),
('Jane', 'Smith', '1988-11-23', 'Female', '+1-555-5678', 'jane.smith@email.com', 'scrypt:32768:8:1$q8fJcO5zG7aK2sP1$a1d17d591871a2a4bc03d157a972cbe0a3a71b69a25b1b4b9b9a6a8a0a9a1a9a', '456 Oak Ave, Shelbyville', 2),
('Robert', 'Johnson', '1960-08-05', 'Male', '+1-555-8765', 'robert.j@email.com', 'scrypt:32768:8:1$q8fJcO5zG7aK2sP1$a1d17d591871a2a4bc03d157a972cbe0a3a71b69a25b1b4b9b9a6a8a0a9a1a9a', '789 Pine Rd, Capital City', 3);

-- 3. Insert Emergency Contacts
INSERT INTO emergency_contacts (patient_id, first_name, last_name, relationship, phone, email) VALUES
(1, 'Mary', 'Doe', 'Spouse', '+1-555-9988', 'mary.doe@email.com'),
(2, 'Thomas', 'Smith', 'Father', '+1-555-7766', 'thomas.smith@email.com'),
(3, 'Alice', 'Johnson', 'Daughter', '+1-555-4433', 'alice.j@email.com');

-- 4. Insert Medicines
INSERT INTO medicines (name, form, strength, manufacturer, description) VALUES
('Atorvastatin', 'Tablet', '20mg', 'Pfizer', 'Cholesterol-lowering medication (statin)'),
('Metformin Hydrochloride', 'Tablet', '500mg', 'Bristol-Myers Squibb', 'Oral diabetes medicine that helps control blood sugar levels'),
('Lisinopril', 'Tablet', '10mg', 'Merck', 'ACE inhibitor used to treat high blood pressure'),
('Albuterol', 'Inhaler', '90mcg', 'GlaxoSmithKline', 'Bronchodilator for asthma relief');

-- 5. Insert Schedules
-- John Doe (Patient 1) takes Atorvastatin (Medicine 1) Daily at 21:00 (9:00 PM) and Lisinopril (Medicine 3) Daily at 08:00 AM
-- Jane Smith (Patient 2) takes Metformin (Medicine 2) Daily at 08:00 AM and 20:00 (8:00 PM)
-- Robert Johnson (Patient 3) has Albuterol Inhaler (Medicine 4) As Needed
INSERT INTO schedules (patient_id, medicine_id, dosage, frequency, reminder_time, start_date, end_date, special_instructions) VALUES
(1, 1, '1 Tablet', 'Daily', '21:00:00', '2026-01-01', NULL, 'Take at bedtime. Do not drink grapefruit juice.'),
(1, 3, '1 Tablet', 'Daily', '08:00:00', '2026-01-01', NULL, 'Take in the morning on an empty stomach.'),
(2, 2, '1 Tablet', 'Daily', '08:00:00', '2026-03-15', '2026-09-15', 'Take with meals.'),
(2, 2, '1 Tablet', 'Daily', '20:00:00', '2026-03-15', '2026-09-15', 'Take with meals.'),
(3, 4, '2 Puffs', 'As Needed', '00:00:00', '2026-05-01', NULL, 'Use for acute shortness of breath or before exercise.');

-- 6. Insert Dose Logs
-- Logs for Patient 1 (John Doe) for yesterday (2026-06-11) and today (2026-06-12)
INSERT INTO dose_logs (schedule_id, scheduled_datetime, status, taken_datetime, notes) VALUES
-- Schedule 1 (Atorvastatin at 21:00)
(1, '2026-06-11 21:00:00', 'Taken', '2026-06-11 21:05:00', 'Took on time, no side effects.'),
(1, '2026-06-12 21:00:00', 'Taken', '2026-06-12 21:15:00', NULL),

-- Schedule 2 (Lisinopril at 08:00)
(2, '2026-06-11 08:00:00', 'Taken', '2026-06-11 08:02:00', NULL),
(2, '2026-06-12 08:00:00', 'Missed', NULL, 'Forgot to carry medicine to work.'),

-- Schedule 3 (Metformin at 08:00)
(3, '2026-06-12 08:00:00', 'Taken', '2026-06-12 08:10:00', 'Taken with breakfast.'),

-- Schedule 4 (Metformin at 20:00)
(4, '2026-06-11 20:00:00', 'Skipped', NULL, 'Skipped due to fast before blood test.');
