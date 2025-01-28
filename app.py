from flask import Flask, render_template, request, jsonify
import os
import yagmail
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

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
    email = request.form.get('email', 'troyburnsfamily@gmail.com')

    # Validate form data
    if not artist_url:
        return jsonify({'status': 'error', 'message': 'Artist URL is required'}), 400
    if not email:
        return jsonify({'status': 'error', 'message': 'Email is required'}), 400

    try:
        # Fetch past events
        past_events = fetch_past_dates_with_pagination(artist_url)

        # If no events are found
        if not past_events:
            return jsonify({
                'status': 'success',
                'message': 'No past events found for this artist.',
                'events': []
            })

        # Prepare email content
        events_list = "\n".join([f"{event['venue']} - {event['datetime']}" for event in past_events])
        body = f"Here are the past events for the artist:\n\n{events_list}"

        # Send the email
        send_email(email, "TourMapper Pro - Past Events", body)

        return jsonify({
            'status': 'success',
            'message': 'Process completed successfully!',
            'events': past_events
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def fetch_past_dates_with_pagination(artist_url):
    """
    Fetch past tour dates from Bandsintown using pagination.
    """
    past_dates = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    current_url = f"{artist_url}?date=past"
    page = 1

    while current_url:
        try:
            print(f"Fetching page {page} of past events from: {current_url}")
            response = requests.get(current_url, headers=headers)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                events = extract_events_from_html(soup)
                if not events:
                    break  # No more events
                past_dates.extend(events)
                current_url = get_next_page_url(soup)  # Logic to get the next page URL
                page += 1
            else:
                raise Exception(f"Error fetching data: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error during pagination: {e}")
            break

    return past_dates

def extract_events_from_html(soup):
    """
    Extract events data from the HTML content.
    """
    events = []
    for event in soup.find_all("div", class_="event-card"):
        venue = event.find("div", class_="venue-name").text.strip()
        datetime = event.find("time")["datetime"]
        events.append({"venue": venue, "datetime": datetime})
    return events

def get_next_page_url(soup):
    """
    Get the URL for the next page of events, if available.
    """
    next_button = soup.find("a", {"rel": "next"})
    if next_button:
        return next_button["href"]
    return None

def send_email(to_email, subject, body):
    """
    Send an email using yagmail with the app password from Heroku config vars.
    """
    try:
        sender_email = "your_email@gmail.com"  # Replace with your email
        sender_password = os.getenv("EMAIL_APP_PASSWORD")  # Get the app password from environment
        with yagmail.SMTP(sender_email, sender_password) as yag:
            yag.send(to=to_email, subject=subject, contents=body)
        print("Email sent successfully")
    except Exception as e:
        print(f"Error sending email: {e}")
        raise

if __name__ == '__main__':
    app.run(debug=True)
