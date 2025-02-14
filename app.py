from flask import Flask, render_template, request, jsonify, send_file
import json
import os

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    print("📥 File Upload Request Received")  # Debugging Log

    if 'file' not in request.files:
        print("❌ No file in request")
        return jsonify({"message": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        print("❌ No file selected")
        return jsonify({"message": "No file selected"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    print(f"✅ File saved successfully: {file_path}")
    return jsonify({"message": f"File '{file.filename}' uploaded successfully"}), 200

@app.route('/download_geojson')
def download_geojson():
    return send_file("polygon.geojson", as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
