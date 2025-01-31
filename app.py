from flask import Flask, request, jsonify, render_template
import logging

# Initialize Flask app
app = Flask(__name__, template_folder="templates")

# Enable logging for debugging
logging.basicConfig(level=logging.DEBUG)

# Store URLs in memory (temporary storage)
stored_urls = []

@app.route('/')
def home():
    """Serve the main HTML page."""
    return render_template("index.html")  # ✅ Ensure index.html is in the 'templates' folder

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

        # Store URLs in memory
        stored_urls.extend(urls)

        logging.info(f"Stored URLs: {stored_urls}")
        return jsonify({"message": "URLs uploaded successfully!"}), 200

    except Exception as e:
        logging.error(f"Upload URLs error: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/view_urls', methods=['GET'])
def view_urls():
    """Endpoint to retrieve stored URLs."""
    return jsonify({"urls": stored_urls})

@app.route('/clear_urls', methods=['POST'])
def clear_urls():
    """Endpoint to clear stored URLs."""
    global stored_urls
    stored_urls = []
    return jsonify({"message": "Stored URLs cleared successfully."})

if __name__ == '__main__':
    app.run(debug=True)
