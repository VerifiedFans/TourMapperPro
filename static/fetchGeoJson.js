function getGeoJson() {
    const address = document.getElementById("address-input").value;
    if (!address) {
        alert("Please enter an address!");
        return;
    }

    fetch("/generate_geojson", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address: address })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert("Error: " + data.error);
        } else {
            alert("GeoJSON file created successfully! Click 'Download GeoJSON' to save.");
        }
    })
    .catch(error => console.error("Error:", error));
}

function downloadGeoJSON() {
    fetch("/download_geojson")
        .then(response => response.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "building.geojson";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        });
}
