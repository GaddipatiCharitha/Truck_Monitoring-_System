from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
import psycopg2.extras
import os
from datetime import datetime, timedelta
from models import get_db_connection, init_db, create_test_data

app = Flask(__name__)
app.secret_key = os.getenv('SESSION_SECRET', 'dev-secret-key-change-in-production')

db_initialized = False

@app.before_request
def initialize_database():
    global db_initialized
    if not db_initialized:
        try:
            init_db()
            create_test_data()
            db_initialized = True
        except Exception as e:
            print(f"Database initialization error: {e}")

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password are required', 'error')
            return render_template('login.html')
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cur.execute('''
        SELECT * FROM trucks 
        WHERE owner_id = %s 
        ORDER BY created_at DESC
    ''', (user_id,))
    trucks = cur.fetchall()
    
    cur.execute('''
        SELECT a.*, t.truck_number 
        FROM alerts a
        JOIN trucks t ON a.truck_id = t.id
        WHERE t.owner_id = %s AND a.is_read = FALSE
        ORDER BY a.created_at DESC
        LIMIT 10
    ''', (user_id,))
    alerts = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('dashboard.html', trucks=trucks, alerts=alerts)

@app.route('/truck/<int:truck_id>')
def truck_detail(truck_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cur.execute('SELECT * FROM trucks WHERE id = %s AND owner_id = %s', (truck_id, user_id))
    truck = cur.fetchone()
    
    if not truck:
        flash('Truck not found or access denied', 'error')
        return redirect(url_for('dashboard'))
    
    cur.execute('SELECT * FROM drivers WHERE truck_id = %s', (truck_id,))
    drivers = cur.fetchall()
    
    cur.execute('''
        SELECT * FROM gps_locations 
        WHERE truck_id = %s 
        ORDER BY timestamp DESC 
        LIMIT 1
    ''', (truck_id,))
    current_location = cur.fetchone()
    
    cur.execute('''
        SELECT * FROM gps_locations 
        WHERE truck_id = %s 
        ORDER BY timestamp DESC 
        LIMIT 50
    ''', (truck_id,))
    travel_history = cur.fetchall()
    
    cur.execute('''
        SELECT fd.*, d.name as driver_name 
        FROM face_detections fd
        LEFT JOIN drivers d ON fd.driver_id = d.id
        WHERE fd.truck_id = %s 
        ORDER BY fd.detected_at DESC 
        LIMIT 10
    ''', (truck_id,))
    face_detections = cur.fetchall()
    
    cur.execute('''
        SELECT * FROM video_recordings 
        WHERE truck_id = %s 
        ORDER BY recorded_at DESC
    ''', (truck_id,))
    recordings = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('truck_detail.html', 
                         truck=truck, 
                         drivers=drivers,
                         current_location=current_location,
                         travel_history=travel_history,
                         face_detections=face_detections,
                         recordings=recordings)

@app.route('/truck/<int:truck_id>/driver/add', methods=['POST'])
def add_driver(truck_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    name = request.form.get('name')
    phone = request.form.get('phone')
    license_number = request.form.get('license_number')
    photo_url = request.form.get('photo_url', '/static/images/default_driver.jpg')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('SELECT owner_id FROM trucks WHERE id = %s', (truck_id,))
    truck = cur.fetchone()
    
    if not truck or truck[0] != session['user_id']:
        cur.close()
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    cur.execute('''
        INSERT INTO drivers (truck_id, name, phone, license_number, photo_url)
        VALUES (%s, %s, %s, %s, %s)
    ''', (truck_id, name, phone, license_number, photo_url))
    
    conn.commit()
    cur.close()
    conn.close()
    
    flash('Driver added successfully', 'success')
    return redirect(url_for('truck_detail', truck_id=truck_id))

@app.route('/truck/<int:truck_id>/driver/<int:driver_id>/edit', methods=['POST'])
def edit_driver(truck_id, driver_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    name = request.form.get('name')
    phone = request.form.get('phone')
    license_number = request.form.get('license_number')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('SELECT owner_id FROM trucks WHERE id = %s', (truck_id,))
    truck = cur.fetchone()
    
    if not truck or truck[0] != session['user_id']:
        cur.close()
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    cur.execute('''
        UPDATE drivers 
        SET name = %s, phone = %s, license_number = %s
        WHERE id = %s AND truck_id = %s
    ''', (name, phone, license_number, driver_id, truck_id))
    
    conn.commit()
    cur.close()
    conn.close()
    
    flash('Driver updated successfully', 'success')
    return redirect(url_for('truck_detail', truck_id=truck_id))

@app.route('/truck/<int:truck_id>/driver/<int:driver_id>/delete', methods=['POST'])
def delete_driver(truck_id, driver_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('SELECT owner_id FROM trucks WHERE id = %s', (truck_id,))
    truck = cur.fetchone()
    
    if not truck or truck[0] != session['user_id']:
        cur.close()
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    cur.execute('DELETE FROM drivers WHERE id = %s AND truck_id = %s', (driver_id, truck_id))
    
    conn.commit()
    cur.close()
    conn.close()
    
    flash('Driver deleted successfully', 'success')
    return redirect(url_for('truck_detail', truck_id=truck_id))

@app.route('/truck/<int:truck_id>/recording/start', methods=['POST'])
def start_recording(truck_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    camera_number = request.form.get('camera_number', 1)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('SELECT owner_id FROM trucks WHERE id = %s', (truck_id,))
    truck = cur.fetchone()
    
    if not truck or truck[0] != session['user_id']:
        cur.close()
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    file_url = f'/static/videos/truck{truck_id}_cam{camera_number}_rec_{datetime.now().strftime("%Y%m%d_%H%M%S")}.mp4'
    
    cur.execute('''
        INSERT INTO video_recordings (truck_id, camera_number, file_url, status)
        VALUES (%s, %s, %s, %s)
    ''', (truck_id, camera_number, file_url, 'recording'))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({'message': 'Recording started', 'file_url': file_url})

@app.route('/truck/<int:truck_id>/recording/<int:recording_id>/stop', methods=['POST'])
def stop_recording(truck_id, recording_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('SELECT owner_id FROM trucks WHERE id = %s', (truck_id,))
    truck = cur.fetchone()
    
    if not truck or truck[0] != session['user_id']:
        cur.close()
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    cur.execute('''
        UPDATE video_recordings 
        SET status = %s, file_size = %s, duration = %s
        WHERE id = %s AND truck_id = %s
    ''', ('saved', 524288000, 3600, recording_id, truck_id))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({'message': 'Recording stopped and saved'})

@app.route('/truck/<int:truck_id>/recording/<int:recording_id>/delete', methods=['POST'])
def delete_recording(truck_id, recording_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('SELECT owner_id FROM trucks WHERE id = %s', (truck_id,))
    truck = cur.fetchone()
    
    if not truck or truck[0] != session['user_id']:
        cur.close()
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    cur.execute('DELETE FROM video_recordings WHERE id = %s AND truck_id = %s', (recording_id, truck_id))
    
    conn.commit()
    cur.close()
    conn.close()
    
    flash('Recording deleted successfully', 'success')
    return redirect(url_for('truck_detail', truck_id=truck_id))

@app.route('/truck/<int:truck_id>/camera/<int:camera_number>/feed')
def camera_feed(truck_id, camera_number):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('SELECT owner_id FROM trucks WHERE id = %s', (truck_id,))
    truck = cur.fetchone()
    
    cur.close()
    conn.close()
    
    if not truck or truck[0] != session['user_id']:
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({
        'truck_id': truck_id,
        'camera_number': camera_number,
        'status': 'live',
        'stream_url': f'/static/videos/live_feed_cam{camera_number}.mp4',
        'message': 'Simulated live camera feed'
    })

@app.route('/alert/<int:alert_id>/mark_read', methods=['POST'])
def mark_alert_read(alert_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('''
        UPDATE alerts 
        SET is_read = TRUE 
        WHERE id = %s
    ''', (alert_id,))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({'message': 'Alert marked as read'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
