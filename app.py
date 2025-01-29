import os
import time
import json
import googlemaps
import yagmail
import simplekml
import requests

from flask import Flask, render_template, request, jsonify, send_from_directory
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)

# Load API Keys
GMAPS_API_KEY = os.getenv("GMAPS_API_KEY")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# Verify API Keys Exist
if not GMAPS_API_KEY:
    raise ValueError("❌ Google Maps API Key is missing! Set it in Heroku.")
if not EMAIL_USER or not EMAIL_PASS:
    raise ValueError("❌ Email credentials missing! Set EMAIL_USER and EMAIL_PASS in Heroku.")

gmaps = googlemaps.Client(key=GMAPS_API_KEY)

# Storage for URLs
URL_FILE = "urls.json"

# Ensure static directory exists
os.makedirs("static", exist_ok=True)

@app.route('/')
def index():
    """Render home page"""
    return render_template("index.html")

@app.route('/upload_urls', methods=['POST'])
def upload_urls():
    """Save uploaded URLs"""
    urls = request.get_json().get("urls", [])
    if not urls:
        return jsonify({"status": "error", "message": "No URLs provided"}), 400

    with open(URL_FILE, "w") as f:
        json.dump(urls, f)

    return jsonify({"status": "success", "message": "URLs uploaded successfully"})

@app.route('/view_urls', methods=['GET'])
def view_urls():
    """Retrieve stored URLs"""
    if not os.path.exists(URL_FILE):
        return jsonify({"status": "error", "message": "No URLs found"}), 404

    with open(URL_FILE, "r") as f:
        urls = json.load(f)

    return jsonify({"status": "success", "urls": urls})

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    """Scrape event data, generate KML & GeoJSON, and send email"""
    if not os.path.exists(URL_FILE):
        return jsonify({"status": "error", "message": "No URLs available"}), 404

    with open(URL_FILE, "r") as f:
        urls = json.load(f)

    if not urls:
        return jsonify({"status": "error", "message": "No valid URLs"}), 400

    # Configure WebDriver
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=chrome_options)

    events = []
    for url in urls:
        try:
            driver.get(url)
            time.sleep(2)  # Allow page to load

            event_data = {
                "date": driver.find_element(By.CSS_SELECTOR, "h2.EfW1v6YNlQnbyB7fUHmR").text,
                "venue": driver.find_element(By.CSS_SELECTOR, "a.q1Vlsw1cdclAUZ4gBvAn").text,
                "address": driver.find_element(By.CSS_SELECTOR, "div:nth-child(1)").text,
                "city_state_zip": driver.find_element(By.CSS_SELECTOR, "div:nth-child(2) a").text,
            }
            
            # Split city, state, zip
            parts = event_data["city_state_zip"].split(", ")
            event_data["city"] = parts[0]
            event_data["state"], event_data["zip"] = parts[1].split(" ")

            # Get Lat/Long
            location_query = f"{event_data['address']}, {event_data['city']}, {event_data['state']} {event_data['zip']}"
            geocode_result = gmaps.geocode(location_query)
            if geocode_result:
                event_data["lat"] = geocode_result[0]["geometry"]["location"]["lat"]
                event_data["lng"] = geocode_result[0]["geometry"]["location"]["lng"]
            else:
                event_data["lat"], event_data["lng"] = None, None

            events.append(event_data)

        except Exception as e:
            print(f"❌ Error scraping {url}: {e}")

    driver.quit()

    if not events:
        return jsonify({"status": "error", "message": "No valid event data found"}), 400

    # Generate KML
    kml = simplekml.Kml()
    for event in events:
        if event["lat"] and event["lng"]:
            kml.newpoint(name=event["venue"], description=event["date"], coords=[(event["lng"], event["lat"])])
    kml.save("static/events.kml")

    # Generate GeoJSON
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [event["lng"], event["lat"]]},
                "properties": {"venue": event["venue"], "date": event["date"]}
            }
            for event in events if event["lat"] and event["lng"]
        ]
    }
    with open("static/events.geojson", "w") as f:
        json.dump(geojson_data, f)

    # Send Email
    try:
        yag = yagmail.SMTP(EMAIL_USER, EMAIL_PASS)
        yag.send(
            to="troyburnsfamily@gmail.com",
            subject="Event Data",
            contents="Attached are the event files.",
            attachments=["static/events.kml", "static/events.geojson"]
        )
        email_status = "Email sent successfully."
    except Exception as e:
        email_status = f"Email failed: {e}"

    return jsonify({"status": "success", "message": "Scraping completed.", "email_status": email_status})

@app.route('/download/<file_type>', methods=['GET'])
def download_file(file_type):
    """Download KML or GeoJSON file"""
    file_name = f"events.{file_type}"
    if os.path.exists(f"static/{file_name}"):
        return send_from_directory("static", file_name, as_attachment=True)
    else:
        return jsonify({"status": "error", "message": f"{file_type.upper()} file not found."}), 404

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

