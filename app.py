from flask import Flask, render_template, request, jsonify, send_file
import os
import zipfile
import requests

app = Flask(__name__)

# Temporary folder to store files
UPLOAD_FOLDER = 'temp'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def fetch_past_dates_from_url(artist_url):
    """Fetch past tour dates directly from the provided Bandsintown artist URL."""
    # Add the date range to the URL for past events
    url_with_dates = f"{artist_url}?date=past"
    
    # Make the HTTP request
    response = requests.get(url_with_dates)
    if response.status_code == 200:
        return response.json()  # Assuming Bandsintown returns JSON
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
        # Step 1: Fetch past dates from the given URL
        past_dates = fetch_past_dates_from_url(artist_url)

        # Step 2: Process the fetched data
        # For simplicity, let's assume we log the events and email them
        events_list = "\n".join([f"{event['venue']['name']} - {event['datetime']}" for event in past_dates])

        # Save the events to a text file
        events_file_path = os.path.join(UPLOAD_FOLDER, 'events.txt')
        with open(events_file_path, 'w') as f:
            f.write(events_list)

        # For now, simulate an email being sent with the events file
        return jsonify({
            'status': 'success',
            'message': 'Process completed successfully!',
            'events': past_dates,
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)

@app.route('/')
def index():
    print("Working Directory:", os.getcwd())
    print("Templates Folder Exists:", os.path.isdir("templates"))
    print("Templates Contents:", os.listdir("templates"))
    return render_template('index.html')

