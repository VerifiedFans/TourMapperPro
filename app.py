import os
import json
import time
import yagmail
import simplekml
import googlemaps
from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)

# Load Google Maps API Key from Environment
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Load Email Credentials
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# Store Uploaded URLs
URL_STORAGE_FILE = "urls.json"


# -----------------------------------------------
# 📌 ROUTES
# -----------------------------------------------
@app.route("/")
def index():
    """Render the homepage."""
    return render_template("index.html")


@app.route("/upload_urls", methods=["POST"])
def upload_urls():
    """Receive a list of URLs from the user and save them."""
    try:
        data = request.get_json()
        urls = data.get("urls", [])

        if not urls:
            return jsonify({"status": "error", "message": "No URLs received"}), 400

        # Save URLs to a file
        with open(URL_STORAGE_FILE, "w") as f:
            json.dump(urls, f)

        return jsonify({"status": "success", "message": "URLs uploaded successfully!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/view_urls", methods=["GET"])
def view_urls():
    """Return the stored URLs."""
    if os.path.exists(URL_STORAGE_FILE):
        with open(URL_STORAGE_FILE, "r") as f:
            urls = json.load(f)
        return jsonify({"status": "success", "urls": urls})
    return jsonify({"status": "error", "message": "No URLs stored"}), 404


@app.route("/start_scraping", methods=["POST"])
def start_scraping():
    """Start scraping events from the stored URLs."""
    try:
        # Load URLs
        if not os.path.exists(URL_STORAGE_FILE):
            return jsonify({"status": "error", "message": "No URLs uploaded"}), 400

        with open(URL_STORAGE_FILE, "r") as f:
            urls = json.load(f)

        if not urls:
            return jsonify({"status": "error", "message": "No URLs found in file"}), 400

        # Configure Chrome WebDriver
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        driver_path = os.getenv("CHROMEDRIVER_PATH", "/app/.chromedriver/bin/chromedriver")
        browser = webdriver.Chrome(driver_path, options=chrome_options)

        events = []
        for url in urls:
            browser.get(url)
            time.sleep(3)  # Allow time for page to load

            try:
                event_data = {
                    "date": browser.find_element(By.CSS_SELECTOR, "h2.EfW1v6YNlQnbyB7fUHmR").text,
                    "venue": browser.find_element(By.CSS_SELECTOR, "a.q1Vlsw1cdclAUZ4gBvAn").text,
                    "address": browser.find_element(By.CSS_SELECTOR, "div:nth-child(1)").text,
                    "city_state_zip": browser.find_element(By.CSS_SELECTOR, "div a[href*='bandsintown.com/c/']").text,
                }

                # Extract City, State, Zip
                city_state_zip_parts = event_data["city_state_zip"].split(" ")
                event_data["city"] = city_state_zip_parts[0].strip().replace(",", "")
                event_data["state"] = city_state_zip_parts[1].strip().replace(",", "")
                event_data["zip"] = city_state_zip_parts[-1].strip()

                # Convert Address to Lat/Long using Google Maps API
                full_address = f"{event_data['address']}, {event_data['city']}, {event_data['state']} {event_data['zip']}"
                geocode_result = gmaps.geocode(full_address)

                if geocode_result:
                    event_data["latitude"] = geocode_result[0]["geometry"]["location"]["lat"]
                    event_data["longitude"] = geocode_result[0]["geometry"]["location"]["lng"]

                events.append(event_data)
            except Exception as e:
                print(f"Error extracting event data from {url}: {e}")

        browser.quit()

        if not events:
            return jsonify({"status": "error", "message": "No valid event data found."}), 400

        # Create KML File
        kml = simplekml.Kml()
        for event in events:
            kml.newpoint(
                name=event["venue"],
                description=f"{event['date']} - {event['address']}",
                coords=[(event["longitude"], event["latitude"])],
            )

        if not os.path.exists("static"):
            os.makedirs("static")

        kml_file = "static/events.kml"
        kml.save(kml_file)

        # Email Results
        try:
            yag = yagmail.SMTP(EMAIL_USER, EMAIL_PASS)
            yag.send(
                to="troyburnsfamily@gmail.com",
                subject="Event Data",
                contents="Attached are your event files.",
                attachments=[kml_file]
            )
        except Exception as e:
            print(f"Email Error: {e}")
            return jsonify({
                "status": "warning",
                "message": "Scraping completed but email failed.",
                "error": str(e)
            }), 500

        return jsonify({"status": "success", "message": "Scraping completed!", "events": events})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
