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
    # Debugging output to verify the templates folder
    print("Current Working Directory:", os.getcwd())
    print("Templates Folder Exists:", os.path.isdir("templates"))
    print("Templates Contents:", os.listdir("templates"))
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_process():
    artist_url = request.form.get('artist_url')
    email = request.form.get('email', 'your-default-email@example.com')

    # Validate input
    if not artist_url:
        return jsonify({'status': 'error', 'message': 'Artist URL is required'}), 400
    if not email:
        return jsonify({'status': 'error', 'message': 'Email is required'}), 400

    try:
        # Fetch all past events
        past_events = fetch_past_dates_with_pagination(artist_url)

        if not past_events:
            return jsonify({
                'status': 'success',
                'message': 'No past events found for this artist.',
                'events': []
            })

        # Optionally, email results (function not shown here)
        # send_email(email, "TourMapper Pro - Past Events", past_events)

        return jsonify({
            'status': 'success',
            'message': 'Process completed successfully!',
            'events': past_events
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def fetch_past_dates_with_pagination(artist_url):
    """
    Fetch all past tour dates from Bandsintown using Selenium to interact with "Show More Dates."
    """
    # Initialize Selenium WebDriver
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run in headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)

    past_events = []
    
    try:
        # Open the artist's past events page
        driver.get(f"{artist_url}?date=past")
        wait = WebDriverWait(driver, 10)

        # Loop through pagination until "Show More Dates" is no longer visible
        while True:
            try:
                # Wait for the "Show More Dates" button and click it
                show_more_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Show More Dates')]"))
                )
                show_more_button.click()
                time.sleep(2)  # Allow time for the new events to load
            except Exception as e:
                print("No more 'Show More Dates' button found:", e)
                break

        # After all events are loaded, parse the page content with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")
        past_events = extract_events_from_html(soup)
    
    except Exception as e:
        print("Error during scraping:", e)
    finally:
        driver.quit()

    return past_events

def extract_events_from_html(soup):
    """
    Extract event details (venue name, date, etc.) from the page content.
    """
    events = []
    event_cards = soup.find_all("div", class_="event-card")  # Update this selector as needed
    for card in event_cards:
        try:
            venue_name = card.find("div", class_="venue-name").get_text(strip=True)
            event_date = card.find("div", class_="event-date").get_text(strip=True)
            event_address = card.find("div", class_="venue-address").get_text(strip=True)
            events.append({
                "venue_name": venue_name,
                "event_date": event_date,
                "event_address": event_address,
            })
        except AttributeError:
            # Skip incomplete cards
            continue
    return events

if __name__ == '__main__':
    app.run(debug=True)
