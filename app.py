from flask import Flask, render_template, request, jsonify
from celery import Celery
import redis
import pandas as pd
import os

app = Flask(__name__)

# **🔗 Connect to Redis**
app.config['CELERY_BROKER_URL'] = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
app.config['CELERY_RESULT_BACKEND'] = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

celery = make_celery(app)

# **📌 Homepage**
@app.route('/')
def index():
    return render_template('index.html')

# **📌 CSV Upload Route**
@app.route('/upload', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    file_path = os.path.join('uploads', file.filename)
    file.save(file_path)

    task = process_csv.delay(file_path)
    return jsonify({'task_id': task.id}), 202

# **📌 Celery Task: Process CSV**
@celery.task(bind=True)
def process_csv(self, file_path):
    df = pd.read_csv(file_path)
    venues = []

    for index, row in df.iterrows():
        venue_data = {
            "name": row["Venue Name"],
            "address": row["Address"],
            "city": row["City"],
            "state": row["State"],
            "zip": row["Zip"],
            "date": row["Date"]
        }
        venues.append(venue_data)
    
    os.remove(file_path)  # Clean up
    return {'status': 'completed', 'venues': venues}

# **📌 Task Status Check**
@app.route('/task-status/<task_id>')
def task_status(task_id):
    task = process_csv.AsyncResult(task_id)
    if task.state == 'PENDING':
        return jsonify({'status': 'Processing...'}), 202
    elif task.state == 'SUCCESS':
        return jsonify({'status': 'Completed', 'data': task.result}), 200
    else:
        return jsonify({'status': 'Error'}), 500

if __name__ == '__main__':
    app.run(debug=True)
