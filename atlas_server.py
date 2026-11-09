import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import requests
from flask import Flask, jsonify, send_from_directory, abort, Response, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTOBAHN_BASE = "https://verkehr.autobahn.de/o/autobahn"

app = Flask(__name__)

@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "atlas_live_erweitert.html")

@app.route("/health")
def health():
    return jsonify({"status": "online", "app": "ATLAS LIVE"})

@app.route("/robots.txt")
def robots_txt():
    # Dynamic host keeps this correct for the Render URL or a later custom domain.
    body = "User-agent: *\nAllow: /\nSitemap: " + request.host_url.rstrip("/") + "/sitemap.xml\n"
    return Response(body, content_type="text/plain; charset=utf-8")


@app.route("/sitemap.xml")
def sitemap_xml():
    # The app currently has one public landing page at /.
    location = request.host_url.rstrip("/") + "/"
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        '<url><loc>' + location + '</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>'
        '</urlset>'
    )
    return Response(body, content_type="application/xml; charset=utf-8")

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


_webcam_cache = {"created": 0.0, "data": {}}
_webcam_cache_lock = Lock()

@app.route("/api/autobahn/webcams")
def autobahn_webcams():
    """Return public Autobahn webcams; cache results briefly and isolate road failures."""
    now = time.time()
    with _webcam_cache_lock:
        if _webcam_cache["data"] and now - _webcam_cache["created"] < 300:
            return jsonify(_webcam_cache["data"])

    try:
        roads_response = requests.get(
            AUTOBAHN_BASE + "/",
            headers={"Accept": "application/json", "User-Agent": "ATLAS-LIVE/1.0"},
            timeout=(3, 7),
        )
        roads_response.raise_for_status()
        roads_payload = roads_response.json()
        roads = roads_payload.get("roads", []) if isinstance(roads_payload, dict) else []
        if not roads:
            return jsonify({"error": "Die Autobahn-API hat keine Straßenliste geliefert."}), 502
    except (requests.RequestException, ValueError):
        return jsonify({"error": "Die Autobahn-Straßenliste ist gerade nicht erreichbar."}), 502

    webcams = []
    failed = 0

    def fetch_road(road):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,12}", str(road)):
            return []
        response = requests.get(
            f"{AUTOBAHN_BASE}/{road}/services/webcam",
            headers={"Accept": "application/json", "User-Agent": "ATLAS-LIVE/1.0"},
            timeout=(4, 12),
        )
        if response.status_code == 204:
            return []
        response.raise_for_status()
        payload = response.json()
        webcams = payload.get("webcam", []) if isinstance(payload, dict) else []
        return webcams if isinstance(webcams, list) else []

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(fetch_road, road) for road in roads]
        for future in as_completed(futures):
            try:
                webcams.extend(future.result())
            except Exception:
                failed += 1

    webcams = [
        camera for camera in webcams
        if isinstance(camera, dict)
        and str(camera.get("isBlocked", "false")).lower() != "true"
        and camera.get("future") is not True
    ]
    result = {
        "webcam": webcams,
        "checked": len(roads),
        "failed": failed,
        "count": len(webcams),
        "source": "Autobahn GmbH",
    }
    with _webcam_cache_lock:
        _webcam_cache["created"] = time.time()
        _webcam_cache["data"] = result
    return jsonify(result)

@app.route("/api/autobahn/roads")
@app.route("/api/autobahn/<road>/services/webcam")
def autobahn_data(road=None):
    if road is None:
        upstream = AUTOBAHN_BASE
    else:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,12}", road):
            abort(400)
        upstream = AUTOBAHN_BASE + "/" + road + "/services/webcam"

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


@app.route("/api/radio/stations")
def radio_stations():
    """Search the public Radio Browser directory; only return secure HTTPS streams."""
    name = request.args.get("name", "").strip()[:80]
    country = request.args.get("country", "").strip()[:80]
    tag = request.args.get("tag", "").strip()[:50]
    try:
        limit = max(1, min(int(request.args.get("limit", "24")), 40))
    except ValueError:
        return jsonify({"error": "Ungültiges Ergebnislimit."}), 400

    params = {"limit": limit, "hidebroken": "true", "order": "votes", "reverse": "true"}
    if name:
        params["name"] = name
    if country:
        params["country"] = country
    if tag:
        params["tag"] = tag
    try:
        response = requests.get(
            "https://de1.api.radio-browser.info/json/stations/search",
            params=params,
            headers={"Accept": "application/json", "User-Agent": "ATLAS-LIVE/1.0 (world radio directory)"},
            timeout=(4, 12),
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Unexpected Radio Browser response")
    except (requests.RequestException, ValueError):
        return jsonify({"error": "Das weltweite Radio-Verzeichnis ist gerade nicht erreichbar."}), 502

    stations = []
    for station in payload:
        if not isinstance(station, dict) or station.get("lastcheckok") != 1:
            continue
        stream = station.get("url_resolved") or station.get("url") or ""
        if not isinstance(stream, str) or not stream.lower().startswith("https://"):
            continue
        stations.append({
            "stationuuid": station.get("stationuuid", ""),
            "name": str(station.get("name") or "Unbekannter Sender")[:160],
            "country": str(station.get("country") or "")[:80],
            "countrycode": str(station.get("countrycode") or "")[:2],
            "geo_lat": station.get("geo_lat"),
            "geo_long": station.get("geo_long"),
            "language": str(station.get("language") or "")[:100],
            "tags": str(station.get("tags") or "")[:180],
            "codec": str(station.get("codec") or "")[:30],
            "bitrate": station.get("bitrate") if isinstance(station.get("bitrate"), int) else 0,
            "homepage": station.get("homepage") if str(station.get("homepage") or "").startswith("https://") else "",
            "stream": stream,
        })
    return jsonify({"stations": stations, "count": len(stations), "source": "Radio Browser"})


@app.route("/api/radio/click/<station_uuid>")
def radio_station_click(station_uuid):
    """Notify Radio Browser when a directory station is played."""
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", station_uuid):
        abort(400)
    try:
        response = requests.get(
            "https://de1.api.radio-browser.info/json/url/" + station_uuid,
            headers={"Accept": "application/json", "User-Agent": "ATLAS-LIVE/1.0 (world radio directory)"},
            timeout=(3, 8),
        )
        response.raise_for_status()
    except requests.RequestException:
        return jsonify({"error": "Sender-Aufruf konnte nicht registriert werden."}), 502
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
