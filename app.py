import os
from flask import Flask, request, jsonify, render_template, send_file, url_for
from flask_dropzone import Dropzone
from celery import Celery
import redis
import csv
import time
from shapely.geometry import Polygon
import geojson

app = Flask(__name__)

# Configure Dropzone
app.config['DROPZONE_UPLOAD_MULTIPLE'] = False
app.config['DROPZONE_ALLOWED_FILE_TYPE'] = 'default'
app.config['DROPZONE_MAX_FILE_SIZE'] = 10

# Configure Celery
app.config['CELERY_BROKER_URL'] = 'rediss://:p321cd2f912b63b15ee8467cedf8986e2f10f0215536ff28bf0d0aff6043617c2@ec2-3-230-61-127'
app.config['CELERY_RESULT_BACKEND'] = 'rediss://:p321cd2f912b63b15ee8467cedf8986e2f10f0215536ff28bf0d0aff6043617c2@ec2-3-230-61-127'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

# Global Variables
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if file:
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        task = process_csv.delay(file_path)
        return jsonify({'task_id': task.id}), 202
    return jsonify({'error': 'No file uploaded'}), 400

@app.route('/task-status/<task_id>')
def task_status(task_id):
    task = process_csv.AsyncResult(task_id)
    if task.state == 'PENDING':
        return jsonify({'state': task.state, 'progress': 0})
    elif task.state != 'FAILURE':
        response = {'state': task.state, 'progress': task.info.get('progress', 0)}
        if 'result' in task.info:
            response['result'] = task.info['result']
        return jsonify(response)
    return jsonify({'state': task.state, 'progress': 0, 'error': str(task.info)}), 500

@app.route('/download', methods=['GET'])
def download():
    file_path = os.path.join(UPLOAD_FOLDER, 'result.geojson')
    return send_file(file_path, as_attachment=True)

@celery.task(bind=True)
def process_csv(self, file_path):
    try:
        polygons = []
        with open(file_path, 'r') as file:
            reader = csv.DictReader(file)
            rows = list(reader)
            total = len(rows)

            for i, row in enumerate(rows):
                venue_polygon = Polygon([
                    (-84.113, 34.418), (-84.112, 34.417),
                    (-84.112, 34.416), (-84.111, 34.416)
                ])
                parking_polygon = Polygon([
                    (-84.115, 34.420), (-84.114, 34.419),
                    (-84.113, 34.418), (-84.115, 34.418)
                ])

                merged_polygon = venue_polygon.union(parking_polygon)
                geojson_feature = geojson.Feature(geometry=geojson.mapping(merged_polygon), properties=row)
                polygons.append(geojson_feature)

                # Update progress
                self.update_state(state='PROGRESS', meta={'progress': int((i + 1) / total * 100)})

        # Save the resulting GeoJSON
        result_path = os.path.join(UPLOAD_FOLDER, 'result.geojson')
        feature_collection = geojson.FeatureCollection(polygons)
        with open(result_path, 'w') as geojson_file:
            geojson.dump(feature_collection, geojson_file)

        return {'progress': 100, 'result': 'GeoJSON file created successfully'}
    except Exception as e:
        return {'progress': 0, 'error': str(e)}

if __name__ == '__main__':
    app.run(debug=True)
