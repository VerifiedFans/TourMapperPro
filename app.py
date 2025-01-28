from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import os

app = Flask(__name__)

@app.route('/')
def index():
    print("Current Working Directory:", os.getcwd())
    print("Templates Folder Exists:", os.path.isdir("templates"))
    print("Templates Contents:", os.listdir("templates"))
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_process():
    artist_url = request.form.get('artist_url')
    email = request.form.get('email', 'your-default-email@example.com')

    if not artist_url:
        return jsonify({'status': 'error', 'message': 'Artist URL is required'}), 400
    if not email:
        return jsonify({'status': 'error', 'message': 'Email is required'}), 400

    try:
        # Scrape past event dates and URLs
        past_events = fetch_past_event_dates_and_urls(artist_url)

        if not past_events:
            return jsonify({
                'status': 'success',
                'message': 'No past events found for this artist.',
                'events': []
            })

        # Optionally: Fetch additional details using event URLs
        detailed_events = fetch_event_details_from_urls(past_events)

        # Return detailed event data
        return jsonify({
            'status': 'success',
            'message': 'Process completed successfully!',
            'events': detailed_events
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def fetch_past_event_dates_and_urls(artist_url):
    """
    Fetch all past event dates and their URLs from the artist's page.
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)

    event_data = []

    try:
        driver.get(f"{artist_url}?date=past")
        wait = WebDriverWait(driver, 10)

        while True:
            try:
                # Click "Show More Dates" button if available
                show_more_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Show More Dates')]"))
                )
                show_more_button.click()
                time.sleep(2)
            except Exception:
                break  # Exit loop if no more "Show More Dates" button is found

        # Parse the loaded HTML
        soup = BeautifulSoup(driver.page_source, "html.parser")
        event_cards = soup.find_all("a", class_="event-link")  # Update selector as needed

        for card in event_cards:
            try:
                date = card.find("div", class_="event-date").get_text(strip=True)
                url = card["href"]  # Extract event URL
                event_data.append({"date": date, "url": url})
            except AttributeError:
                continue  # Skip incomplete cards
    finally:
        driver.quit()

    return event_data

def fetch_event_details_from_urls(events):
    """
    Fetch additional details for each event using its URL.
    """
    detailed_events = []

    for event in events:
        try:
            response = requests.get(event['url'])
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                venue_name = soup.find("div", class_="venue-name").get_text(strip=True)
                address = soup.find("div", class_="venue-address").get_text(strip=True)

                # Update the event data with details
                event['venue_name'] = venue_name
                event['address'] = address
                detailed_events.append(event)
            else:
                print(f"Failed to fetch details for {event['url']}")
        except Exception as e:
            print(f"Error fetching details for {event['url']}: {e}")

    return detailed_events

if __name__ == '__main__':
    app.run(debug=True)
