from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import yagmail
import os
import time
import simplekml
from zipfile import ZipFile

app = Flask(__name__)

# Email configuration (update if needed)
EMAIL = os.getenv("EMAIL", "your-email@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

@app.route('/')
def index():
    # Debugging output to verify templates
    print("Current Working Directory:", os.getcwd())
    print("Templates Folder Exists:", os.path.isdir("templates"))
    print("Templates Contents:", os.listdir("templates"))
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_process():
    artist_url = request.form.get('artist_url')
    email = request.form.get('email', EMAIL)

    if not artist_url:
        return jsonify({'status': 'error', 'message': 'Artist URL is required'}), 400
    if not email:
        return jsonify({'status': 'error', 'message': 'Email is required'}), 400

    try:
        # Fetch all past events and details
        past_events = fetch_past_dates_with_details(artist_url)

        if not past_events:
            return jsonify({
                'status': 'success',
                'message': 'No past events found for this artist.',
                'events': []
            })

        # Generate KML and GeoJSON files
        kml_file, geojson_file = generate_files(past_events)

        # Email the generated files
        send_email(email, "TourMapper Pro - Event Details", "Attached are the event files.", [kml_file, geojson_file])

        return jsonify({
            'status': 'success',
            'message': 'Process completed successfully!',
            'events': past_events
        })

    except Exception as e:
        print(f"Error during process: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def fetch_past_dates_with_details(artist_url):
    """
    Scrape Bandsintown for past event details.
    """
    events = []
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        driver.get(artist_url)
        time.sleep(3)

        # Navigate to "Past" events
        past_button = driver.find_element("xpath", "//a[contains(text(), 'Past')]")
        past_button.click()
        time.sleep(2)

        while True:
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            # Find event rows
            event_rows = soup.find_all('div', class_='eventRow')
            for row in event_rows:
                event = {
                    'venue': row.find('div', class_='eventVenue').text.strip(),
                    'date': row.find('div', class_='eventDate').text.strip(),
                    'location': row.find('div', class_='eventLocation').text.strip(),
                    'url': row.find('a', class_='eventLink')['href']
                }
                events.append(event)

            # Check for "Show More Dates" button
