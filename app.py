from flask import Flask, render_template, request, jsonify, send_file
import os
import zipfile
import requests

app = Flask(__name__)

# Temporary folder to store files
UPLOAD_FOLDER = 'temp'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Bandsintown API Key
BANDSINTOWN_API_KEY = "your_api_key_here"  # Replace with your actual API key


def fetch_past_dates(artist_url):
    """Fetch past tour dates for an artist using the Bandsintown API."""
    # Extract artist name from the URL
    artist_name = artist_url.split("/")[-1]
    api_url = f"https://rest.bandsintown.com/artists/{artist_name}/events"
    
    # Make the API request
    response = requests.get(api_url, params={"app_id": BANDSINTOWN_API_KEY, "date": "past"})
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error fetching data: {response.status_code} - {response.text}")


@app.route('/')
def index():
    return render_template('index.html')  # Simple dashboard HTML with logo


@app.route('/start', methods=['POST'])
def start_process():
    artist_url = request.form.get('artist_url')
    email = request.form.get('email', 'troyburnsfamily@gmail.com')

    try:
        # Step 1: Fetch PAST dates from Bandsintown
        past_dates = fetch_past_dates(artist_url)

        # For demonstration, we just return the fetched events
        return jsonify({
            'status': 'success',
            'events': past_dates
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


if __name__ == '__main__':
    app.run