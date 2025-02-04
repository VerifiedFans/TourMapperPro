import os
import time
import json
import redis
import requests
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from celery import Celery
from kombu import Exchange, Queue
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# **✅ Configure Redis & Celery**
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")  # Default if REDIS_URL is not set
CELERY_BROKER_URL = REDIS_URL.replace("rediss://", "redis://")  # Fix SSL issue
CELERY_RESULT_BACKEND = CELERY_BROKER_URL

celery = Celery(app.name, broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    broker_transport_options={"visibility_timeout": 3600},  # Prevent timeout issues
    task_queues=(Queue("default", Exchange("default"), routing_key="default"),),
)

# **✅ Redis Connection**
try:
    redis_client = redis.from_url(CELERY_BROKER_URL)
    redis_client.ping()
    print("✅ Redis Connected Successfully!")
except redis.ConnectionError:
    print("❌ Redis Connection Failed!")

# **📂 File Upload Configuration**
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"txt", "csv"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# **🚀 Celery Task: Process URLs**
@celery.task(bind=True)
def process_urls(self, urls):
    results = []
    
    for index, url in enumerate(urls):
        try:
            response = requests.get(url, timeout=5)
            data = {"url": url, "status": response.status_code, "content_length": len(response.text)}
            results.append(data)
        except requests.exceptions.RequestException as e:
            results.append({"url": url, "error": str(e)})

        # Update task progress
        self.update_state(state="PROGRESS", meta={"current": index + 1, "total": len(urls)})
        time.sleep(1)  # Simulate delay

    output_file = os.path.join(UPLOAD_FOLDER, "processed_urls.json")
    with open(output_file, "w") as f:
        json.dump(results, f)

    return {"status": "Completed", "file": output_file}

# **📤 Upload Endpoint**
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        # Read URLs from file
        with open(filepath, "r") as f:
            urls = [line.strip() for line in f if line.strip()]

        # Start Celery task
        task = process_urls.apply_async(args=[urls])
        return jsonify({"task_id": task.id}), 202

    return jsonify({"error": "Invalid file type"}), 400

# **📊 Task Status**
@app.route("/task-status/<task_id>", methods=["GET"])
def task_status(task_id):
    task = process_urls.AsyncResult(task_id)
    if task.state == "PENDING":
        response = {"state": task.state, "progress": 0}
    elif task.state != "FAILURE":
        response = {"state": task.state, "progress": task.info.get("current", 0) / task.info.get("total", 1) * 100}
    else:
        response = {"state": "FAILED", "error": str(task.info)}

    return jsonify(response)

# **📥 Download Processed File**
@app.route("/download", methods=["GET"])
def download_file():
    filepath = os.path.join(UPLOAD_FOLDER, "processed_urls.json")
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({"error": "File not found"}), 404

# **🌍 Home Route**
@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
