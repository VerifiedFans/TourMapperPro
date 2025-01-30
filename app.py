from flask import Flask, request, jsonify
import logging

app = Flask(__name__)

# Enable logging
logging.basicConfig(level=logging.DEBUG)

URLS_FILE = "urls.txt"

def save_urls(urls):
    """Save URLs to a file for persistence."""
    try:
        with open(URLS_FILE, "a") as file:
            for url in urls:
                file.write(url + "\n")
        return True
    except Exception as e:
        logging.error(f"Error saving URLs: {str(e)}")
        return False

def load_urls():
    """Load URLs from the file."""
    try:
        with open(URLS_FILE, "r") as file:
            return [line.strip() for line in file.readlines()]
    except FileNotFoundError:
        return []
    except Exception as e:
        logging.error(f"Error reading URLs: {str(e)}")
        return []

@app.route('/upload_urls', methods=['POST'])
def upload_urls():
    """Endpoint to receive and store URLs."""
    try:
        logging.debug(f"Headers: {request.headers}")
        logging.debug(f"Raw Data: {request.data}")

        data = request.get_json()
        logging.debug(f"Parsed JSON: {data}")

        if not data or 'urls' not in data:
            return jsonify({"message": "Invalid request. No URLs received."}), 400
        
        urls = data['urls']
        if not isinstance(urls, list) or not all(isinstance(url, str) for url in urls):
            return jsonify({"message": "Invalid data format. Expecting a list of URLs."}), 400
        
        if save_urls(urls):
            return jsonify({"message": "URLs uploaded successfully!"}), 200
        else:
            return jsonify({"message": "Error saving URLs."}), 500

    except Exception as e:
        logging.error(f"Upload URLs error: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/view_urls', methods=['GET'])
def view_urls():
    """Endpoint to retrieve stored URLs."""
    urls = load_urls()
    return jsonify({"urls": urls})

@app.route('/clear_urls', methods=['POST'])
def clear_urls():
    """Endpoint to clear stored URLs."""
    try:
        with open(URLS_FILE, "w") as file:
            file.write("")  # Clear the file
        return jsonify({"message": "Stored URLs cleared successfully."})
    except Exception as e:
        logging.error(f"Error clearing URLs: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/')
def home():
    return "Tourmapper Pro API is running!"

if __name__ == '__main__':
    app.run(debug=True)
