import os
import re

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

@app.route("/api/autobahn/roads")
@app.route("/api/autobahn/<road>/services/webcam")
def autobahn_data(road=None):
    if road is None:
        upstream = AUTOBahn_BASE + "/roads"
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
