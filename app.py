import os
import json
import googlemaps
import yagmail
import simplekml
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Load API Key for Google Maps Geocoding
GMAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
if not GMAPS_API_KEY:
    raise ValueError("Google Maps API Key is missing! Set it in Heroku environment variables.")

gmaps = googlemaps.Client(key=GMAPS_API_KEY)

URL_FILE = "urls.txt"

def load_urls():
    """Load stored venue URLs from a text file."""
    if os.path.exists(URL_FILE):
        with open(URL_FILE, "r") as file:
            return [line.strip() for line in file.readlines()]
    return []

def save_urls(urls):
    """Save venue URLs to a text file."""
    with open(URL_FILE, "w") as file:
        file.write("\n".join(urls))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_urls', methods=['POST'])
def upload_urls():
    """Upload venue URLs for processing."""
    data = request.get_json()
    urls = data.get("urls", [])
    if not urls:
        return jsonify({"status": "error", "message": "No URLs provided"}), 400

    save_urls(urls)
    return jsonify({"status": "success", "message": "URLs successfully uploaded!"})

@app.route('/view_urls', methods=['GET'])
def view_urls():
    """Retrieve stored venue URLs."""
    urls = load_urls()
    return jsonify({"status": "success", "urls": urls})

@app.route('/clear_urls', methods=['POST'])
def clear_urls():
    """Clear stored URLs."""
    save_urls([])
    return jsonify({"status": "success", "message": "URLs cleared successfully"})

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    """Scrape stored venue URLs and geocode event locations."""
    urls = load_urls()
    if not urls:
        return jsonify({"status": "error", "message": "No stored URLs to scrape"}), 400

    events = []
    errors = []

    for url in urls:
        try:
            # Simulated data (Replace with Selenium scraping logic)
            event = {
                "date": "Dec 7, 2024",
                "venue": "Jamie Foxx Performing Arts Center",
                "address": "400 Poetry Rd",
                "city_state": "Terrell, TX",
                "zip": "75160"
            }

            full_address = f"{event['address']}, {event['city_state']} {event['zip']}"

            # Try geocoding the address
            try:
                geocode_result = gmaps.geocode(full_address)
                if geocode_result:
                    location = geocode_result[0]["geometry"]["location"]
                    event["latitude"] = location["lat"]
                    event["longitude"] = location["lng"]
                else:
                    raise ValueError("Geocoding failed, no results returned.")

            except googlemaps.exceptions.ApiError as e:
                errors.append(f"Geocoding API error for {full_address}: {e}")
                continue

            except Exception as e:
                errors.append(f"Unexpected geocoding error for {full_address}: {e}")
                continue

            events.append(event)

        except Exception as e:
            errors.append(f"Error processing {url}: {e}")

    if errors:
        return jsonify({"status": "error", "message": "Some errors occurred", "errors": errors}), 500

    # Generate KML & GeoJSON files
    kml = simplekml.Kml()
    geojson = {"type": "FeatureCollection", "features": []}

    for event in events:
        if event["latitude"] and event["longitude"]:
            kml.newpoint(name=event["venue"], coords=[(event["longitude"], event["latitude"])])
            geojson["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [event["longitude"], event["latitude"]]},
                "properties": event
            })

    kml.save("static/events.kml")
    with open("static/events.geojson", "w") as geojson_file:
        json.dump(geojson, geojson_file)

    # Send email with attachments
    try:
        yag = yagmail.SMTP(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASS'))
        yag.send(
            to='troyburnsfamily@gmail.com',
            subject='Event Data',
            contents='Attached are your KML & GeoJSON files.',
            attachments=["static/events.kml", "static/events.geojson"]
        )
    except Exception as e:
        return jsonify({"status": "warning", "message": "Scraping completed but email failed.", "error": str(e)})

    return jsonify({"status": "success", "message": "Scraping completed successfully!", "events": events})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
