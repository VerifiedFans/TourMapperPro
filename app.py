import os
import time
import json
from flask import Flask, render_template, request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import yagmail
import simplekml
import googlemaps

app = Flask(__name__)

# Initialize Google Maps Client
google_maps_api_key = os.getenv('GOOGLE_MAPS_API_KEY')
gmaps = googlemaps.Client(key=google_maps_api_key)

@app.route('/')
def index():
    """Render the home page."""
    return render_template('index.html')

@app.route('/upload_urls', methods=['POST'])
def upload_urls():
    """Handle the upload of venue URLs."""
    try:
        data = request.get_json()
        urls = data.get('urls', [])
        if not urls:
            return json.dumps({"status": "error", "message": "No URLs provided."}), 400
        
        with open('urls.json', 'w') as f:
            json.dump(urls, f)
        
        return json.dumps({"status": "success", "message": "URLs uploaded successfully."})
    except Exception as e:
        print(f"Error uploading URLs: {e}")
        return json.dumps({"status": "error", "message": str(e)})

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    """Start scraping data from the uploaded URLs."""
    try:
        with open('urls.json', 'r') as f:
            urls = json.load(f)
        
        if not urls:
            return json.dumps({"status": "error", "message": "No URLs to process."}), 400

        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')

        driver_path = os.getenv('CHROMEDRIVER_PATH', '/app/.chromedriver/bin/chromedriver')
        browser = webdriver.Chrome(options=chrome_options)

        events = []
        for url in urls:
            event_data = scrape_venue_data(browser, url)
            if event_data:
                events.append(event_data)

        browser.quit()

        if not events:
            return json.dumps({"status": "success", "message": "No valid event data found.", "events": []})

        kml_file = generate_kml(events)
        geojson_file = generate_geojson(events)

        yag = yagmail.SMTP(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASS'))
        yag.send(
            to='troyburnsfamily@gmail.com',
            subject='Event Data',
            contents='Attached are the KML and GeoJSON files with event data.',
            attachments=[kml_file, geojson_file]
        )

        return json.dumps({"status": "success", "message": "Scraping completed successfully.", "events": events})
    
    except Exception as e:
        print(f"Unhandled error: {e}")
        return json.dumps({"status": "error", "message": str(e)})

def scrape_venue_data(browser, url):
    """Scrape event data from a venue page."""
    try:
        browser.get(url)
        time.sleep(2)

        # Corrected CSS Selectors (Replace with actual values)
        venue_name = browser.find_element(By.CSS_SELECTOR, ".venue-name-selector").text
        event_date = browser.find_element(By.CSS_SELECTOR, ".event-date-selector").text
        address = browser.find_element(By.CSS_SELECTOR, ".event-address-selector").text
        city = browser.find_element(By.CSS_SELECTOR, ".event-city-selector").text
        state = browser.find_element(By.CSS_SELECTOR, ".event-state-selector").text
        zip_code = browser.find_element(By.CSS_SELECTOR, ".event-zip-selector").text

        # Geocode Address
        full_address = f"{address}, {city}, {state} {zip_code}"
        geocode_result = gmaps.geocode(full_address)

        if geocode_result:
            lat = geocode_result[0]['geometry']['location']['lat']
            lng = geocode_result[0]['geometry']['location']['lng']
        else:
            lat, lng = 0, 0

        return {
            "venue_name": venue_name,
            "event_date": event_date,
            "address": address,
            "city": city,
            "state": state,
            "zip": zip_code,
            "latitude": lat,
            "longitude": lng,
            "full_address": full_address
        }
    except Exception as e:
        print(f"Error scraping URL {url}: {e}")
        return None

def generate_kml(events):
    """Generate KML file from event data."""
    kml = simplekml.Kml()
    for event in events:
        kml.newpoint(
            name=event['venue_name'],
            description=event['event_date'],
            coords=[(event['longitude'], event['latitude'])]
        )
    kml_file = "events.kml"
    kml.save(kml_file)
    return kml_file

def generate_geojson(events):
    """Generate GeoJSON file from event data."""
    features = []
    for event in events:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [event['longitude'], event['latitude']]
            },
            "properties": {
                "venue_name": event['venue_name'],
                "event_date": event['event_date'],
                "address": event['address'],
                "city": event['city'],
                "state": event['state'],
                "zip": event['zip']
            }
        })
    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }
    geojson_file = "events.geojson"
    with open(geojson_file, 'w') as f:
        json.dump(geojson_data, f, indent=4)
    return geojson_file

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
