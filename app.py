import os
import time
import json
from flask import Flask, render_template, request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import yagmail
import simplekml
import googlemaps

app = Flask(__name__)

# Initialize Google Maps Client
google_maps_api_key = os.getenv('GOOGLE_MAPS_API_KEY')
gmaps = googlemaps.Client(key=google_maps_api_key)

@app.route('/')
def index():
    """Render the home page."""
    return render_template('index.html')

@app.route('/upload_urls', methods=['POST'])
def upload_urls():
    """Handle the upload of venue URLs."""
    try:
        data = request.get_json()
        urls = data.get('urls', [])
        if not urls:
            return json.dumps({"status": "error", "message": "No URLs provided."}),
