function initMap() {
    const venueCoords = { lat: 40.7505045, lng: -73.9934387 };
    const parkingCoords = { lat: 40.7488933, lng: -73.9899767 };

    const map = new google.maps.Map(document.getElementById("map"), {
        zoom: 15,
        center: venueCoords,
    });

    const polygonCoords = [
        venueCoords,
        { lat: venueCoords.lat - 0.001, lng: venueCoords.lng + 0.001 },
        { lat: parkingCoords.lat - 0.001, lng: parkingCoords.lng - 0.001 },
        { lat: parkingCoords.lat + 0.001, lng: parkingCoords.lng + 0.001 },
    ];

    const polygon = new google.maps.Polygon({
        paths: polygonCoords,
        strokeColor: "#FF0000",
        strokeOpacity: 0.8,
        strokeWeight: 2,
        fillColor: "#FF0000",
        fillOpacity: 0.35,
    });

    polygon.setMap(map);
}

function downloadGeoJSON() {
    fetch('/download_geojson')
        .then(response => response.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'polygon.geojson';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        });
}
