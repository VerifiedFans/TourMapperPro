
from flask import Flask, render_template, request, jsonify
import os
import requests
import simplekml
import zipfile
from email.message import EmailMessage
import smtplib

app = Flask(__name__)

# Ensure temp directory exists
UPLOAD_FOLDER = 'temp'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

def fetch_past_dates_with_pagination(artist_url):
    """Fetch all past events from Bandsintown using pagination."""
    events = []
    page = 1
    while True:
        paginated_url = f"{artist_url}?date=past&page={page}"
        response = requests.get(paginated_url)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {response.status_code} - {response.text}")
        data = response.json()
        if not data:
            break
        events.extend(data)
        page += 1
    return events

def create_kml_files(events, output_folder):
    """Create KML files for all venues."""
    kml_files = []
    for event in events:
        venue_name = event['venue']['name']
        venue_address = event['venue']['address']
        event_date = event['datetime']
        
        # Create a KML file for each venue
        kml = simplekml.Kml()
        kml.newpoint(name=f"{venue_name} - {event_date}", description=venue_address)
        kml_file_path = os.path.join(output_folder, f"{venue_name.replace(' ', '_')}.kml")
        kml.save(kml_file_path)
        kml_files.append(kml_file_path)
    return kml_files

def send_email_with_files(recipient_email, zip_file_path):
    """Send the email with the zip file attached."""
    email = EmailMessage()
    email['Subject'] = "TourMapper Pro - GeoJSON Files"
    email['From'] = "your_email@example.com"  # Replace with your email
    email['To'] = recipient_email
    email.set_content("Attached are the GeoJSON files for the past events.")

    with open(zip_file_path, 'rb') as f:
        email.add_attachment(f.read(), maintype='application', subtype='zip', filename='geojson_files.zip')

    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        smtp.starttls()
        smtp.login('your_email@example.com', 'your_password')  # Use an app-specific password
        smtp.send_message(email)

@app.route('/start', methods=['POST'])
def start_process():
    artist_url = request.form.get('artist_url')
    email = request.form.get('email', 'troyburnsfamily@gmail.com')

    if not artist_url:
        return jsonify({'status': 'error', 'message': 'Artist URL is required'}), 400
    if not email:
        return jsonify({'status': 'error', 'message': 'Email is required'}), 400

    try:
        # Step 1: Fetch past dates
        past_events = fetch_past_dates_with_pagination(artist_url)

        # Step 2: Create KML files
        kml_files = create_kml_files(past_events, UPLOAD_FOLDER)

        # Step 3: Zip KML files
        zip_file_path = os.path.join(UPLOAD_FOLDER, 'geojson_files.zip')
        with zipfile.ZipFile(zip_file_path, 'w') as zipf:
            for file in kml_files:
                zipf.write(file, os.path.basename(file))

        # Step 4: Send email
        send_email_with_files(email, zip_file_path)

        return jsonify({
            'status': 'success',
            'message': 'Process completed successfully!',
            'events': past_events
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
