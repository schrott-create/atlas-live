import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from flask import Flask, jsonify, send_from_directory, abort, Response

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTOBahn_BASE = "https://verkehr.autobahn.de/o/autobahn"

app = Flask(__name__)

@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "atlas_live_erweitert.html")

@app.route("/health")
def health():
    return jsonify({"status": "online", "app": "ATLAS LIVE"})

@app.route("/api/fintraffic/stations")
def fintraffic_stations():
    upstream = "https://tie.digitraffic.fi/api/weathercam/v1/stations"
    try:
        response = requests.get(
            upstream,
            headers={
                "Accept": "application/json",
                "Digitraffic-User": "ATLAS-LIVE/1.0 (public webcam map)",
                "Accept-Encoding": "gzip",
            },
            timeout=25,
        )
        response.raise_for_status()
    except requests.RequestException:
        return jsonify({"error": "Fintraffic-Daten sind gerade nicht erreichbar."}), 502

    return Response(
        response.content,
        status=response.status_code,
        content_type=response.headers.get("Content-Type", "application/json"),
    )


@app.route("/api/autobahn/webcams")
def autobahn_webcams():
    """Fetch webcam lists from motorway roads concurrently, with a bounded timeout."""
    try:
        roads_response = requests.get(
            AUTOBahn_BASE + "/",
            headers={"Accept": "application/json", "User-Agent": "ATLAS-LIVE/1.0"},
            timeout=10,
        )
        roads_response.raise_for_status()
        roads = roads_response.json().get("roads", [])
    except (requests.RequestException, ValueError):
        return jsonify({"error": "Die Autobahn-Straßenliste ist gerade nicht erreichbar."}), 502

    webcams = []
    failed = 0

    def fetch_road(road):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,12}", str(road)):
            return []
        response = requests.get(
            f"{AUTOBahn_BASE}/{road}/services/webcam",
            headers={"Accept": "application/json", "User-Agent": "ATLAS-LIVE/1.0"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("webcam", []) if isinstance(payload, dict) else []

    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(fetch_road, road): road for road in roads}
        for future in as_completed(futures):
            try:
                webcams.extend(future.result())
            except Exception:
                failed += 1

    return jsonify({"webcam": webcams, "checked": len(roads), "failed": failed})

@app.route("/api/autobahn/roads")
@app.route("/api/autobahn/<road>/services/webcam")
def autobahn_data(road=None):
    if road is None:
        upstream = AUTOBahn_BASE
    else:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,12}", road):
            abort(400)
        upstream = AUTOBahn_BASE + "/" + road + "/services/webcam"

    try:
        response = requests.get(
            upstream,
            headers={"Accept": "application/json", "User-Agent": "ATLAS-LIVE/1.0"},
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException:
        return jsonify({"error": "Die öffentliche Autobahn-Datenquelle ist gerade nicht erreichbar."}), 502

    return Response(
        response.content,
        status=response.status_code,
        content_type=response.headers.get("Content-Type", "application/json"),
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
