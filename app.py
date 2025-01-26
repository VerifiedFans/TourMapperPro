from flask import Flask, render_template, request, jsonify, send_file
import os
import zipfile
from bandsintown_api import fetch_past_dates
from google_earth_kml import create_kml_files
from kml_to_geojson import convert_kml_to_geojson
from email_service import send_email

app = Flask(__name__)

# Temporary folder to store files
UPLOAD_FOLDER = 'temp'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')  # Simple dashboard HTML with logo

@app.route('/start', methods=['POST'])
def start_process():
    artist_url = request.form.get('artist_url')
    email = request.form.get('email', 'troyburnsfamily@gmail.com')

    try:
        # Step 1: Fetch PAST dates from Bandsintown
        past_dates = fetch_past_dates(artist_url)

        # Step 2: Generate KML files
        kml_files = create_kml_files(past_dates, UPLOAD_FOLDER)

        # Step 3: Convert KML to GeoJSON
        geojson_files = convert_kml_to_geojson(kml_files, UPLOAD_FOLDER)

        # Step 4: Zip the GeoJSON files
        zip_file_path = os.path.join(UPLOAD_FOLDER, 'geojson_files.zip')
        with zipfile.ZipFile(zip_file_path, 'w') as zipf:
            for file in geojson_files:
                zipf.write(file, os.path.basename(file))

        # Step 5: Send the zip file via email
        send_email(email, zip_file_path)

        return jsonify({
            'status': 'success',
            'message': 'Process completed successfully!',
            'download_url': f'/download/{os.path.basename(zip_file_path)}'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({'status': 'error', 'message': 'File not found.'})

if __name__ == '__main__':
    app.run