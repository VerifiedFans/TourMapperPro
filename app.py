import os
import time
import json
import ssl
from flask import Flask, render_template, request, jsonify, send_file
from celery import Celery

# Initialize Flask app
app = Flask(__name__)

# Fix for Redis SSL connection
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Redis & Celery Configuration (Fixing SSL issue)
app.config['CELERY_BROKER_URL'] = redis_url
app.config['CELERY_RESULT_BACKEND'] = redis_url
app.config['CELERY_REDIS_BACKEND_USE_SSL'] = {
    'ssl_cert_reqs': ssl.CERT_NONE  # Set this to CERT_REQUIRED for higher security
}

# Initialize Celery
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(
    broker_use_ssl={'ssl_cert_reqs': ssl.CERT_NONE},  # Disable strict SSL
    redis_backend_use_ssl={'ssl_cert_reqs': ssl.CERT_NONE}
)

# Folder for processed files
UPLOAD_FOLDER = 'processed_files'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return render_template('index.html')

@celery.task(bind=True)
def process_urls(self, urls):
    """Simulate scraping URLs and generating a GeoJSON file"""
    results = []
    
    for i, url in enumerate(urls):
        time.sleep(2)  # Simulating processing delay
        results.append({"url": url, "status": "Processed", "lat": 40.7128, "lon": -74.0060})
        self.update_state(state='PROGRESS', meta={'current': i + 1, 'total': len(urls)})

    # Save results as GeoJSON
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"url": entry["url"]},
                "geometry": {"type": "Point", "coordinates": [entry["lon"], entry["lat"]]},
            }
            for entry in results
        ],
    }

    geojson_filename = os.path.join(UPLOAD_FOLDER, f"processed_{int(time.time())}.geojson")
    with open(geojson_filename, "w") as geojson_file:
        json.dump(geojson_data, geojson_file)

    return {"status": "Completed", "geojson_file": geojson_filename}

@app.route('/upload', methods=['POST'])
def upload():
    urls = request.json.get('urls', [])
    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    task = process_urls.apply_async(args=[urls])
    return jsonify({"task_id": task.id, "status": "Processing"}), 202

@app.route('/task-status/<task_id>')
def task_status(task_id):
    task = process_urls.AsyncResult(task_id)
    if task.state == 'PROGRESS':
        return jsonify({"state": task.state, "progress": task.info})
    elif task.state == 'SUCCESS':
        return jsonify({"state": task.state, "geojson_file": task.result["geojson_file"]})
    else:
        return jsonify({"state": task.state})

@app.route('/download/<filename>')
def download(filename):
    return send_file(os.path.join(UPLOAD_FOLDER, filename), as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
