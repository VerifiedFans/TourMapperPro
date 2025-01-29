import os
import json
import time
import yagmail
import simplekml
import googlemaps
from flask import Flask, render_template, request, jsonify, send_from_directory
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)

# Load API Keys
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# Storage Path
URL_STORAGE_FILE = "urls.json"
STATIC_DIR = "static"
KML_FILE = "events.kml"
GEOJSON_FILE = "events.geojson"

# Ensure Static Folder Exists
os.makedirs(STATIC_DIR, exist_ok=True)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload_urls", methods=["POST"])
def upload_urls():
    try:
        data = request.get_json()
        urls = data.get("urls", [])

        if not urls:
            return jsonify({"status": "error", "message": "No URLs received"}), 400

        with open(URL_STORAGE_FILE, "w") as f:
            json.dump(urls, f)

        return jsonify({"status": "success", "message": "URLs uploaded successfully!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/view_urls", methods=["GET"])
def view_urls():
    if os.path.exists(URL_STORAGE_FILE):
        with open(URL_STORAGE_FILE, "r") as f:
            urls = json.load(f)
        return jsonify({"status": "success", "urls": urls})
    return jsonify({"status": "error", "message": "No URLs stored"}), 404


@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    try:
        if not os.path.exists(URL_STORAGE_FILE):
            return jsonify({"status": "error", "message": "No URLs uploaded"}), 400

        with open(URL_STORAGE_FILE, "r") as f:
            urls = json.load(f)

        if not urls:
            return jsonify({"status": "error", "message": "No URLs found in file"}), 400

        # Set up ChromeDriver
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--single-process")
        chrome_options.add_argument("--window-size=1280x1024")

        driver_path = os.getenv("CHROMEDRIVER_PATH", "/app/.chromedriver/bin/chromedriver")
        service = Service(driver_path)

        events = []

        for url in urls:
            try:
                browser = webdriver.Chrome(service=service, options=chrome_options)
                browser.get(url)
                time.sleep(3)

                event_data = {
                    "date": browser.find_element(By.CSS_SELECTOR, "h2.EfW1v6YNlQnbyB7fUHmR").text,
                    "venue": browser.find_element(By.CSS_SELECTOR, "a.q1Vlsw1cdclAUZ4gBvAn").text,
                    "address": browser.find_element(By.CSS_SELECTOR, "div:nth-child(1)").text,
                    "city_state_zip": browser.find_element(By.CSS_SELECTOR, "div a[href*='bandsintown.com/c/']").text,
                }

                city_state_zip_parts = event_data["city_state_zip"].split(" ")
                event_data["city"] = city_state_zip_parts[0].strip().replace(",", "")
                event_data["state"] = city_state_zip_parts[1].strip().replace(",", "")
                event_data["zip"] = city_state_zip_parts[-1].strip()

                # Geocode Address
                full_address = f"{event_data['address']}, {event_data['city']}, {event_data['state']} {event_data['zip']}"
                geocode_result = gmaps.geocode(full_address)

                if geocode_result:
                    event_data["latitude"] = geocode_result[0]["geometry"]["location"]["lat"]
                    event_data["longitude"] = geocode_result[0]["geometry"]["location"]["lng"]

                events.append(event_data)

                browser.quit()

            except Exception as e:
                print(f"❌ ERROR extracting event data from {url}: {e}")

        if not events:
            return jsonify({"status": "error", "message": "No valid event data found."}), 400

        # Generate KML
        kml = simplekml.Kml()
        for event in events:
            kml.newpoint(
                name=event["venue"],
                description=f"{event['date']} - {event['address']}",
                coords=[(event["longitude"], event["latitude"])],
            )

        kml.save(os.path.join(STATIC_DIR, KML_FILE))

        # Convert to GeoJSON
        geojson_data = {
            "type": "FeatureCollection",
            "features": []
        }

        for event in events:
            geojson_data["features"].append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [event["longitude"], event["latitude"]]
                },
                "properties": {
                    "name": event["venue"],
                    "date": event["date"],
                    "address": event["address"],
                    "city": event["city"],
                    "state": event["state"],
                    "zip": event["zip"]
                }
            })

        with open(os.path.join(STATIC_DIR, GEOJSON_FILE), "w") as f:
            json.dump(geojson_data, f)

        # Email Results
        try:
            yag = yagmail.SMTP(EMAIL_USER, EMAIL_PASS)
            yag.send(
                to="troyburnsfamily@gmail.com",
                subject="Event Data",
                contents="Attached are your event files.",
                attachments=[os.path.join(STATIC_DIR, KML_FILE), os.path.join(STATIC_DIR, GEOJSON_FILE)]
            )
        except Exception as e:
            print(f"❌ EMAIL ERROR: {e}")
            return jsonify({
                "status": "warning",
                "message": "Scraping completed but email failed.",
                "error": str(e)
            }), 500

        return jsonify({"status": "success", "message": "Scraping completed!", "events": events})

    except Exception as e:
        print(f"❌ SERVER ERROR: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/download_kml")
def download_kml():
    """Serve the KML file."""
    if os.path.exists(os.path.join(STATIC_DIR, KML_FILE)):
        return send_from_directory(STATIC_DIR, KML_FILE, as_attachment=True)
    return jsonify({"status": "error", "message": "KML file not found"}), 404


@app.route("/download_geojson")
def download_geojson():
    """Serve the GeoJSON file."""
    if os.path.exists(os.path.join(STATIC_DIR, GEOJSON_FILE)):
        return send_from_directory(STATIC_DIR, GEOJSON_FILE, as_attachment=True)
    return jsonify({"status": "error", "message": "GeoJSON file not found"}), 404


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
