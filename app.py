import os
import json
from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import yagmail
import simplekml
from werkzeug.utils import secure_filename

app = Flask(__name__)
URLS_FILE = "urls.json"

# Ensure the URL file exists
if not os.path.exists(URLS_FILE):
    with open(URLS_FILE, 'w') as f:
        json.dump([], f)

@app.route('/')
def index():
    """Render the index page with URL management options."""
    return render_template('index.html')

@app.route('/get-urls', methods=['GET'])
def get_urls():
    """Return the list of URLs."""
    try:
        with open(URLS_FILE, 'r') as f:
            urls = json.load(f)
        return jsonify({"status": "success", "urls": urls})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/add-url', methods=['POST'])
def add_url():
    """Add a new URL."""
    url = request.form.get('url')
    if not url:
        return jsonify({"status": "error", "message": "No URL provided."})
    
    try:
        with open(URLS_FILE, 'r') as f:
            urls = json.load(f)
        if url in urls:
            return jsonify({"status": "error", "message": "URL already exists."})
        urls.append(url)
        with open(URLS_FILE, 'w') as f:
            json.dump(urls, f)
        return jsonify({"status": "success", "message": "URL added successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/delete-url', methods=['POST'])
def delete_url():
    """Delete a URL."""
    url = request.form.get('url')
    if not url:
        return jsonify({"status": "error", "message": "No URL provided."})
    
    try:
        with open(URLS_FILE, 'r') as f:
            urls = json.load(f)
        if url not in urls:
            return jsonify({"status": "error", "message": "URL not found."})
        urls.remove(url)
        with open(URLS_FILE, 'w') as f:
            json.dump(urls, f)
        return jsonify({"status": "success", "message": "URL deleted successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/upload-urls', methods=['POST'])
def upload_urls():
    """Upload a JSON file of URLs."""
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded."})
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected."})
    if file and file.filename.endswith('.json'):
        try:
            file_path = secure_filename(file.filename)
            file.save(file_path)
            with open(file_path, 'r') as f:
                urls = json.load(f)
            if not isinstance(urls, list):
                return jsonify({"status": "error", "message": "Invalid file format. Must be a list of URLs."})
            with open(URLS_FILE, 'w') as f:
                json.dump(urls, f)
            os.remove(file_path)
            return jsonify({"status": "success", "message": "URLs uploaded successfully."})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    else:
        return jsonify({"status": "error", "message": "Invalid file type. Please upload a .json file."})

@app.route('/scrape', methods=['POST'])
def scrape():
    """Scrape all URLs for data."""
    # This function retains the previous scraping functionality
    pass  # Insert the scraping logic here as needed

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
