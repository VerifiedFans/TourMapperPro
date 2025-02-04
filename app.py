
import os
import json
import redis
from flask import Flask, request, jsonify, render_template, send_file
from celery import Celery
from werkzeug.utils import secure_filename

# Initialize Flask app
app = Flask(__name__)

# ✅ Fetch Redis URL from Heroku Config Vars (Fixes SSL Cert Issue)
REDIS_URL = os.getenv("REDIS_URL")
CELERY_BROKER_URL = f"{REDIS_URL}?ssl_cert_reqs=CERT_NONE"
CELERY_RESULT_BACKEND = f"{REDIS_URL}?ssl_cert_reqs=CERT_NONE"

# ✅ Configure Celery
celery = Celery(app.name, broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
celery.conf.update(task_serializer="json", accept_content=["json"], result_serializer="json")

# ✅ Set Upload Folder
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# 📌 Home Route (Renders Upload UI)
@app.route("/")
def home():
    return render_template("index.html")


# 📌 Upload Handler Route
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files and "text_data" not in request.form:
        return jsonify({"error": "No file or text data provided"}), 400

    # ✅ Handle File Upload
    if "file" in request.files:
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        # 📌 Start Celery Background Task
        task = process_urls.delay(filepath, "file")
        return jsonify({"task_id": task.id}), 202

    # ✅ Handle Copy-Paste Text Upload
    elif "text_data" in request.form:
        text_data = request.form["text_data"]
        temp_filepath = os.path.join(app.config["UPLOAD_FOLDER"], "temp_urls.txt")

        with open(temp_filepath, "w") as f:
            f.write(text_data)

        # 📌 Start Celery Background Task
        task = process_urls.delay(temp_filepath, "text")
        return jsonify({"task_id": task.id}), 202


# 📌 Celery Task to Process URLs
@celery.task(bind=True)
def process_urls(self, filepath, source_type):
    try:
        urls = []
        if source_type == "file":
            with open(filepath, "r") as f:
                urls = f.read().splitlines()
        elif source_type == "text":
            urls = filepath.split("\n")

        # Simulate Processing (Replace with actual scraping logic)
        results = [{"url": url, "status": "Processed"} for url in urls]

        # ✅ Save GeoJSON Output
        output_filename = "output.geojson"
        output_path = os.path.join(app.config["UPLOAD_FOLDER"], output_filename)
        with open(output_path, "w") as f:
            json.dump(results, f)

        return {"status": "Completed", "download_url": f"/download/{output_filename}"}

    except Exception as e:
        return {"status": "Failed", "error": str(e)}


# 📌 Route to Check Task Status
@app.route("/task-status/<task_id>")
def task_status(task_id):
    task = process_urls.AsyncResult(task_id)
    if task.state == "PENDING":
        response = {"status": "Processing"}
    elif task.state == "SUCCESS":
        response = task.result
    else:
        response = {"status": "Failed", "error": str(task.info)}
    return jsonify(response)


# 📌 Route to Download Processed GeoJSON
@app.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    return send_file(file_path, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
