
import os
import json
import csv
from flask import Flask, request, render_template, jsonify, send_file
from werkzeug.utils import secure_filename
import requests
import time

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
ALLOWED_EXTENSIONS = {'txt', 'csv'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

# Ensure upload & processed directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Store uploaded URLs
uploaded_urls = []

def allowed_file(filename):
    """Check if the file is allowed (TXT or CSV)."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_urls(file_path):
    """Extract URLs from TXT or CSV files."""
    urls = []
    with open(file_path, 'r', encoding='utf-8') as file:
        if file_path.endswith('.csv'):
            reader = csv.reader(file)
            headers = next(reader, None)  # Read header if present
            url_index = headers.index("url") if headers and "url" in headers else 0
            for row in reader:
                if row and len(row) > url_index:
                    urls.append(row[url_index].strip())
        else:
            urls = [line.strip() for line in file if line.strip()]
    return urls

@app.route('/')
def index():
    return render_template('index.html', uploaded_files=uploaded_urls)

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        global uploaded_urls
        uploaded_urls = extract_urls(file_path)

        return jsonify({'message': 'File uploaded successfully', 'urls': uploaded_urls})
    
    return jsonify({'error': 'Invalid file format'}), 400

@app.route('/view_files', methods=['GET'])
def view_uploaded_files():
    """View uploaded URLs."""
    return jsonify({'uploaded_urls': uploaded_urls})

@app.route('/clear_files', methods=['POST'])
def clear_uploaded_files():
    """Clear uploaded URLs."""
    global uploaded_urls
    uploaded_urls = []
    return jsonify({'message': 'Uploaded files cleared successfully'})

def get_coordinates(venue_name):
    """Get coordinates for a venue using an external API."""
    api_url = f"https://nominatim.openstreetmap.org/search?q={venue_name}&format=json"
    response = requests.get(api_url)
    data = response.json()
    if data:
        return float(data[0]['lon']), float(data[0]['lat'])
    return None

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    """Scrape URLs and generate GeoJSON."""
    if not uploaded_urls:
        return jsonify({'error': 'No URLs to process'}), 400
    
    geojson_data = {
        "type": "FeatureCollection",
        "features": []
    }

    for idx, url in enumerate(uploaded_urls):
        venue_name = f"Venue {idx + 1}"  # Placeholder for venue name
        coordinates = get_coordinates(venue_name) or (0, 0)  # Default to (0,0) if not found

        geojson_data["features"].append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [coordinates[0], coordinates[1]]
            },
            "properties": {
                "url": url,
                "venue_name": venue_name
            }
        })

        time.sleep(1)  # Simulate scraping time

    geojson_path = os.path.join(app.config['PROCESSED_FOLDER'], 'data.geojson')
    with open(geojson_path, 'w', encoding='utf-8') as geojson_file:
        json.dump(geojson_data, geojson_file, indent=4)

    return jsonify({'message': 'Scraping completed', 'geojson': geojson_path})

@app.route('/download_geojson', methods=['GET'])
def download_geojson():
    """Download the generated GeoJSON file."""
    geojson_path = os.path.join(app.config['PROCESSED_FOLDER'], 'data.geojson')
    if not os.path.exists(geojson_path):
        return jsonify({'error': 'No GeoJSON file found'}), 400
    return send_file(geojson_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
