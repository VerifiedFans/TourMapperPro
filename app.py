from flask import Flask, render_template, request, jsonify
import os
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
import simplekml
from shapely.geometry import Point, Polygon
import geopy.distance
from yagmail import SMTP

app = Flask(__name__)

# Helper function to generate polygons around venues
def generate_polygon(latitude, longitude, distance_meters=100):
    """
    Generate a polygon around a given point to represent a venue and parking area.
    """
    center = Point(longitude, latitude)
    polygon_coords = []

    # Create a square polygon around the center
    for angle in [0, 90, 180, 270]:
        offset = geopy.distance.distance(meters=distance_meters).destination(
            (latitude, longitude), bearing=angle
        )
        polygon_coords.append((offset[1], offset[0]))

    return Polygon(polygon_coords)

# Helper function to generate KML and GeoJSON files
def generate_files_with_polygons(event_data):
    """
    Generate KML and GeoJSON files with polygons for each venue.
    """
    kml = simplekml.Kml()

    for event in event_data:
        # Generate polygon for the venue
        latitude, longitude = event['latitude'], event['longitude']
        venue_polygon = generate_polygon(latitude, longitude)

        # Add polygon to the KML
        pol = kml.newpolygon(
            name=f"{event['artist']} - {event['venue']}",
            outerboundaryis=[
                (point[1], point[0]) for point in venue_polygon.exterior.coords
            ],
        )
        pol.style.polystyle.color = simplekml.Color.changealpha('80', simplekml.Color.red)

    kml_path = "venues_with_polygons.kml"
    kml.save(kml_path)

    # For now, return only KML file
    return kml_path

# Helper function to send email
def send_email(recipient_email, subject, body, file_path):
    """
    Send an email with the generated files attached.
    """
    try:
        yag = SMTP('your-email@gmail.com', 'your-app-password')
        yag.send(
            to=recipient_email,
            subject=subject,
            contents=body,
            attachments=file_path
        )
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")
        raise

# Helper function to scrape past events
def scrape_artist_past_events(artist_url):
    """
    Scrape past event URLs from the artist's Bandsintown page.
    """
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    service = Service(executable_path="/app/.chromedriver/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get(artist_url)
        driver.find_element(By.LINK_TEXT, "Past").click()

        # Collect all event URLs
        event_urls = []
        while True:
            soup = BeautifulSoup(driver.page_source, "html.parser")
            events = soup.find_all("a", class_="event-url-class")  # Update this based on actual class names
            event_urls.extend([event['href'] for event in events])

            # Check for "Show More Dates" and click it
            try:
                show_more = driver.find_element(By.LINK_TEXT, "Show More Dates")
                show_more.click()
            except:
                break

        return event_urls
    finally:
        driver.quit()

# Helper function to scrape event details
def scrape_event_details(event_url):
    """
    Scrape event details from the individual event page.
    """
    response = requests.get(event_url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract event details (example, update selectors as needed)
    artist_name = soup.find("h1", class_="artist-name-class").text.strip()
    venue_name = soup.find("h2", class_="venue-name-class").text.strip()
    date = soup.find("div", class_="date-class").text.strip()
    address = soup.find("div", class_="address-class").text.strip()

    # Extract latitude and longitude if available (use appropriate selectors)
    latitude = float(soup.find("meta", {"property": "latitude"})['content'])
    longitude = float(soup.find("meta", {"property": "longitude"})['content'])

    return {
        "artist": artist_name,
        "venue": venue_name,
        "date": date,
        "address": address,
        "latitude": latitude,
        "longitude": longitude,
    }

@app.route('/')
def index():
    # Debugging information
    print("Current Working Directory:", os.getcwd())
    print("Templates Folder Exists:", os.path.isdir("templates"))
    print("Templates Contents:", os.listdir("templates"))
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_process():
    artist_url = request.form.get('artist_url')
    email = request.form.get('email', 'default-email@example.com')

    if not artist_url or not email:
        return jsonify({'status': 'error', 'message': 'Artist URL and email are required.'}), 400

    try:
        # Step 1: Scrape artist's past events
        event_urls = scrape_artist_past_events(artist_url)

        if not event_urls:
            return jsonify({'status': 'success', 'message': 'No past events found for this artist.'})

        # Step 2: Scrape details of each event
        event_data = []
        for url in event_urls:
            event_details = scrape_event_details(url)
            event_data.append(event_details)

        # Step 3: Generate KML and GeoJSON files
        kml_path = generate_files_with_polygons(event_data)

        # Step 4: Send the files via email
        send_email(
            recipient_email=email,
            subject="TourMapper Pro - Venue Map",
            body="Attached are the venue maps.",
            file_path=kml_path
        )

        return jsonify({'status': 'success', 'message': 'Process completed successfully!', 'events': event_data})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
