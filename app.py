import os
import json
import time
import googlemaps
import simplekml
import yagmail
from flask import Flask, render_template, request, jsonify, send_from_directory
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Initialize Flask App
app = Flask(__name__)

# Load Google Maps API Key from Heroku Environment
GMAPS_API_KEY = os.getenv("GMAPS_API_KEY")

if not GMAPS_API_KEY:
    print("❌ Google Maps API Key is missing!")
else:
    print("✅ Google Maps API Key loaded successfully.")

# Initialize Google Maps client
gmaps = googlemaps.Client(key=GMAPS_API_KEY)

# Load Email Credentials
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# Directory for Storing Files
STATIC_DIR = os.path.join(os.getcwd(), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

# Store URLs
urls_file = os.path.join(STATIC_DIR, "urls.txt")


# 🔹 **Home Route**
@app.route("/")
def index():
    return render_template("index.html")


# 🔹 **Upload URLs**
@app.route("/upload_urls", methods=["POST"])
def upload_urls():
    urls = request.form.get("urls")
    if not urls:
        return jsonify({"status": "error", "message": "No URLs provided"}), 400

    with open(urls_file, "w") as f:
        f.write(urls.strip())

    return jsonify({"status": "success", "message": "URLs uploaded successfully"})


# 🔹 **View Stored URLs**
@app.route("/view_urls", methods=["GET"])
def view_urls():
    if not os.path.exists(urls_file):
        return jsonify({"status": "success", "urls": []})

    with open(urls_file, "r") as f:
        urls = f.read().strip().split("\n")

    return jsonify({"status": "success", "urls": urls})


# 🔹 **Clear URLs**
@app.route("/clear_urls", methods=["POST"])
def clear_urls():
    if os.path.exists(urls_file):
        os.remove(urls_file)
    return jsonify({"status": "success", "message": "Stored URLs cleared"})


# 🔹 **Start Scraping**
@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    """Scrapes event data and generates KML & GeoJSON files."""
    try:
        if not os.path.exists(urls_file):
            return jsonify({"status": "error", "message": "No URLs stored"}), 400

        with open(urls_file, "r") as f:
            urls = f.read().strip().split("\n")

        if not urls:
            return jsonify({"status": "error", "message": "No URLs found"}), 400

        # Configure Selenium ChromeDriver
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        driver_path = os.getenv("CHROMEDRIVER_PATH", "/app/.chromedriver/bin/chromedriver")
        browser = webdriver.Chrome(options=chrome_options)

        # Scrape Data
        events = []
        for url in urls:
            browser.get(url)
            time.sleep(2)  # Allow page to load

            try:
                # Extract Event Details
                event_date = browser.find_element(By.CSS_SELECTOR, "h2.EfW1v6YNlQnbyB7fUHmR").text
                venue = browser.find_element(By.CSS_SELECTOR, "a.q1Vlsw1cdclAUZ4gBvAn").text
                location = browser.find_element(By.CSS_SELECTOR, "a[href*='utm_campaign=city_link']").text
                address = browser.find_element(By.CSS_SELECTOR, "div:nth-of-type(1)").text
                zip_code = browser.find_element(By.CSS_SELECTOR, "div:nth-of-type(2)").text.split()[-1]

                # Convert Address to Lat/Lon
                full_address = f"{address}, {location} {zip_code}"
                geocode_result = gmaps.geocode(full_address)

                if geocode_result:
                    lat = geocode_result[0]["geometry"]["location"]["lat"]
                    lon = geocode_result[0]["geometry"]["location"]["lng"]
                else:
                    lat, lon = None, None

                events.append({
                    "date": event_date,
                    "venue": venue,
                    "address": address,
                    "location": location,
                    "zip": zip_code,
                    "latitude": lat,
                    "longitude": lon,
                    "url": url
                })
            except Exception as e:
                print(f"❌ Error scraping {url}: {e}")

        browser.quit()

        if not events:
            return jsonify({"status": "error", "message": "No valid event data found."})

        # **Generate KML File**
        kml = simplekml.Kml()
        for event in events:
            if event["latitude"] and event["longitude"]:
                kml.newpoint(name=event["venue"], description=event["date"],
                             coords=[(event["longitude"], event["latitude"])])

        kml_file = os.path.join(STATIC_DIR, "events.kml")
        kml.save(kml_file)

        # **Generate GeoJSON File**
        geojson_data = {
            "type": "FeatureCollection",
            "features": []
        }

        for event in events:
            if event["latitude"] and event["longitude"]:
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [event["longitude"], event["latitude"]]
                    },
                    "properties": {
                        "venue": event["venue"],
                        "date": event["date"],
                        "address": event["address"],
                        "location": event["location"],
                        "zip": event["zip"],
                        "url": event["url"]
                    }
                }
                geojson_data["features"].append(feature)

        geojson_file = os.path.join(STATIC_DIR, "events.geojson")
        with open(geojson_file, "w") as f:
            json.dump(geojson_data, f)

        # **Send Email**
        if EMAIL_USER and EMAIL_PASS:
            yag = yagmail.SMTP(EMAIL_USER, EMAIL_PASS)
            yag.send(to="troyburnsfamily@gmail.com",
                     subject="Tourmapper Pro Event Data",
                     contents="Attached are the event data files.",
                     attachments=[kml_file, geojson_file])
            print("✅ Email Sent Successfully!")
        else:
            print("❌ Email Credentials Missing, Skipping Email.")

        return jsonify({"status": "success", "message": "Scraping completed!", "events": events})

    except Exception as e:
        print(f"❌ SERVER ERROR: {e}")
        return jsonify({"status": "error", "message": str(e)})


# 🔹 **Download KML File**
@app.route("/static/events.kml", methods=["GET"])
def download_kml():
    return send_from_directory(STATIC_DIR, "events.kml", as_attachment=True)


# 🔹 **Download GeoJSON File**
@app.route("/static/events.geojson", methods=["GET"])
def download_geojson():
    return send_from_directory(STATIC_DIR, "events.geojson", as_attachment=True)


# 🔹 **Run App**
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
