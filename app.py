def process_csv(csv_file):
    """Reads CSV, finds lat/lon, creates polygons, and saves GeoJSON"""
    df = pd.read_csv(csv_file)

    required_columns = {'venue_name', 'address', 'city', 'state', 'zip', 'date'}
    if not required_columns.issubset(df.columns):
        return None

    features = []
    batch_size = 50  # Google API rate limiting
    address_count = 0  # Debug counter

    for index, row in df.iterrows():
        full_address = f"{row['address']}, {row['city']}, {row['state']} {row['zip']}"
        lat, lon = None, None
        print(f"🔍 Processing address {index+1}: {full_address}")  # Debugging

        # ✅ Check Redis cache first
        if cache:
            cached_location = cache.get(full_address)
            if cached_location:
                lat, lon = json.loads(cached_location)
                print(f"✅ Cache hit for {full_address}: ({lat}, {lon})")  # Debugging
        
        # ✅ If not cached, geocode using Google Maps API
        if not lat or not lon:
            try:
                geocode_result = gmaps.geocode(full_address)
                if not geocode_result:
                    print(f"⚠️ No geocode result for: {full_address}")
                    continue  # Skip invalid addresses

                lat = geocode_result[0]['geometry']['location']['lat']
                lon = geocode_result[0]['geometry']['location']['lng']
                print(f"📍 Geocoded {full_address} → ({lat}, {lon})")  # Debugging

                if cache:
                    cache.set(full_address, json.dumps([lat, lon]), ex=86400)  # Cache for 1 day

            except Exception as e:
                print(f"❌ Geocoding error for {full_address}: {e}")
                continue  # Skip errors and move to next address

        # ✅ Create Venue Polygon (Slightly adjusted per venue)
        venue_poly = Polygon([
            (lon - 0.0003, lat - 0.0003),
            (lon + 0.0003, lat - 0.0003),
            (lon + 0.0003, lat + 0.0003),
            (lon - 0.0003, lat + 0.0003),
            (lon - 0.0003, lat - 0.0003)
        ])

        # ✅ Create Parking Polygon (Offset from venue)
        parking_poly = Polygon([
            (lon - 0.0006, lat - 0.0006),
            (lon + 0.0006, lat - 0.0006),
            (lon + 0.0006, lat + 0.0006),
            (lon - 0.0006, lat + 0.0006),
            (lon - 0.0006, lat - 0.0006)
        ])

        # ✅ Add venue & parking polygons to GeoJSON
        features.append({
            "type": "Feature",
            "geometry": mapping(venue_poly),
            "properties": {"name": row['venue_name'], "type": "venue", "address": full_address}
        })
        features.append({
            "type": "Feature",
            "geometry": mapping(parking_poly),
            "properties": {"name": row['venue_name'], "type": "parking", "address": full_address}
        })

        address_count += 1

        if (index + 1) % batch_size == 0:
            time.sleep(1)  # ✅ Prevents Google API rate limit errors

    # ✅ Save GeoJSON File
    geojson_data = {"type": "FeatureCollection", "features": features}
    geojson_filename = os.path.join(OUTPUT_FOLDER, f"venues_{int(time.time())}.geojson")
    
    with open(geojson_filename, "w") as f:
        json.dump(geojson_data, f)

    print(f"✅ {address_count} locations processed. GeoJSON saved as: {geojson_filename}")
    return geojson_filename
