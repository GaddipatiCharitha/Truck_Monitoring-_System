import psycopg2
import psycopg2.extras
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

def get_db_connection():
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('DROP TABLE IF EXISTS video_recordings CASCADE')
    cur.execute('DROP TABLE IF EXISTS alerts CASCADE')
    cur.execute('DROP TABLE IF EXISTS face_detections CASCADE')
    cur.execute('DROP TABLE IF EXISTS gps_locations CASCADE')
    cur.execute('DROP TABLE IF EXISTS drivers CASCADE')
    cur.execute('DROP TABLE IF EXISTS trucks CASCADE')
    cur.execute('DROP TABLE IF EXISTS users CASCADE')
    
    cur.execute('''
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            full_name VARCHAR(150) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE trucks (
            id SERIAL PRIMARY KEY,
            truck_number VARCHAR(50) NOT NULL,
            owner_id INTEGER REFERENCES users(id),
            license_plate VARCHAR(50),
            model VARCHAR(100),
            status VARCHAR(50) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE drivers (
            id SERIAL PRIMARY KEY,
            truck_id INTEGER REFERENCES trucks(id) ON DELETE CASCADE,
            name VARCHAR(150) NOT NULL,
            phone VARCHAR(20),
            license_number VARCHAR(50),
            photo_url VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE gps_locations (
            id SERIAL PRIMARY KEY,
            truck_id INTEGER REFERENCES trucks(id) ON DELETE CASCADE,
            latitude DECIMAL(10, 8) NOT NULL,
            longitude DECIMAL(11, 8) NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE face_detections (
            id SERIAL PRIMARY KEY,
            truck_id INTEGER REFERENCES trucks(id) ON DELETE CASCADE,
            driver_id INTEGER REFERENCES drivers(id) ON DELETE SET NULL,
            image_url VARCHAR(255),
            confidence DECIMAL(5, 2),
            match_result VARCHAR(50),
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE alerts (
            id SERIAL PRIMARY KEY,
            truck_id INTEGER REFERENCES trucks(id) ON DELETE CASCADE,
            alert_type VARCHAR(100) NOT NULL,
            message TEXT NOT NULL,
            severity VARCHAR(20) DEFAULT 'medium',
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE video_recordings (
            id SERIAL PRIMARY KEY,
            truck_id INTEGER REFERENCES trucks(id) ON DELETE CASCADE,
            camera_number INTEGER NOT NULL,
            file_url VARCHAR(255),
            file_size BIGINT,
            duration INTEGER,
            status VARCHAR(50) DEFAULT 'saved',
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    cur.close()
    conn.close()

def create_test_data():
    conn = get_db_connection()
    cur = conn.cursor()
    
    users_data = [
        ('john_doe', generate_password_hash('password123'), 'john@trucking.com', 'John Doe'),
        ('jane_smith', generate_password_hash('password123'), 'jane@trucking.com', 'Jane Smith'),
        ('mike_wilson', generate_password_hash('password123'), 'mike@trucking.com', 'Mike Wilson'),
        ('sarah_jones', generate_password_hash('password123'), 'sarah@trucking.com', 'Sarah Jones')
    ]
    
    for username, password_hash, email, full_name in users_data:
        cur.execute(
            'INSERT INTO users (username, password_hash, email, full_name) VALUES (%s, %s, %s, %s)',
            (username, password_hash, email, full_name)
        )
    
    trucks_data = [
        ('TRK-001', 1, 'ABC-1234', 'Volvo FH16', 'active'),
        ('TRK-002', 1, 'XYZ-5678', 'Scania R450', 'active'),
        ('TRK-003', 2, 'DEF-9012', 'Mercedes Actros', 'active'),
        ('TRK-004', 2, 'GHI-3456', 'MAN TGX', 'active'),
        ('TRK-005', 3, 'JKL-7890', 'DAF XF', 'active'),
        ('TRK-006', 4, 'MNO-2345', 'Iveco Stralis', 'active')
    ]
    
    for truck_number, owner_id, license_plate, model, status in trucks_data:
        cur.execute(
            'INSERT INTO trucks (truck_number, owner_id, license_plate, model, status) VALUES (%s, %s, %s, %s, %s)',
            (truck_number, owner_id, license_plate, model, status)
        )
    
    drivers_data = [
        (1, 'Robert Johnson', '+1-555-0101', 'DL-12345', '/static/images/driver1.jpg'),
        (1, 'Michael Brown', '+1-555-0102', 'DL-23456', '/static/images/driver2.jpg'),
        (2, 'David Garcia', '+1-555-0103', 'DL-34567', '/static/images/driver3.jpg'),
        (3, 'James Martinez', '+1-555-0104', 'DL-45678', '/static/images/driver4.jpg'),
        (4, 'William Rodriguez', '+1-555-0105', 'DL-56789', '/static/images/driver5.jpg'),
        (5, 'Thomas Davis', '+1-555-0106', 'DL-67890', '/static/images/driver6.jpg'),
        (6, 'Charles Miller', '+1-555-0107', 'DL-78901', '/static/images/driver7.jpg')
    ]
    
    for truck_id, name, phone, license_number, photo_url in drivers_data:
        cur.execute(
            'INSERT INTO drivers (truck_id, name, phone, license_number, photo_url) VALUES (%s, %s, %s, %s, %s)',
            (truck_id, name, phone, license_number, photo_url)
        )
    
    gps_data = [
        (1, 40.7128, -74.0060),
        (2, 34.0522, -118.2437),
        (3, 41.8781, -87.6298),
        (4, 29.7604, -95.3698),
        (5, 33.4484, -112.0740),
        (6, 39.7392, -104.9903)
    ]
    
    for truck_id, lat, lon in gps_data:
        cur.execute(
            'INSERT INTO gps_locations (truck_id, latitude, longitude) VALUES (%s, %s, %s)',
            (truck_id, lat, lon)
        )
    
    alerts_data = [
        (1, 'Alcohol Detection', 'Alcohol detected in cabin of TRK-001', 'high', False),
        (2, 'Unauthorized Driver', 'Face detection detected unauthorized person driving TRK-002', 'high', False),
        (3, 'Camera Offline', 'Camera 2 in TRK-003 is not receiving signal', 'medium', False),
        (1, 'Speed Alert', 'TRK-001 exceeded speed limit on Highway 101', 'medium', True),
        (4, 'Camera Offline', 'Camera 1 in TRK-004 connection lost', 'medium', False)
    ]
    
    for truck_id, alert_type, message, severity, is_read in alerts_data:
        cur.execute(
            'INSERT INTO alerts (truck_id, alert_type, message, severity, is_read) VALUES (%s, %s, %s, %s, %s)',
            (truck_id, alert_type, message, severity, is_read)
        )
    
    face_detections_data = [
        (1, 1, '/static/images/face_detect1.jpg', 95.5, 'Matched'),
        (2, 3, '/static/images/face_detect2.jpg', 88.2, 'Matched'),
        (3, 4, '/static/images/face_detect3.jpg', 45.1, 'No Match'),
        (4, 5, '/static/images/face_detect4.jpg', 92.7, 'Matched')
    ]
    
    for truck_id, driver_id, image_url, confidence, match_result in face_detections_data:
        cur.execute(
            'INSERT INTO face_detections (truck_id, driver_id, image_url, confidence, match_result) VALUES (%s, %s, %s, %s, %s)',
            (truck_id, driver_id, image_url, confidence, match_result)
        )
    
    video_recordings_data = [
        (1, 1, '/static/videos/truck1_cam1_rec1.mp4', 524288000, 3600, 'saved'),
        (1, 2, '/static/videos/truck1_cam2_rec1.mp4', 498073600, 3600, 'saved'),
        (2, 1, '/static/videos/truck2_cam1_rec1.mp4', 536870912, 3600, 'saved'),
        (3, 3, '/static/videos/truck3_cam3_rec1.mp4', 471859200, 3600, 'saved')
    ]
    
    for truck_id, camera_number, file_url, file_size, duration, status in video_recordings_data:
        cur.execute(
            'INSERT INTO video_recordings (truck_id, camera_number, file_url, file_size, duration, status) VALUES (%s, %s, %s, %s, %s, %s)',
            (truck_id, camera_number, file_url, file_size, duration, status)
        )
    
    conn.commit()
    cur.close()
    conn.close()
