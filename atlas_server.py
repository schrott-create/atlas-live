
from flask import Flask, send_from_directory, jsonify
import os

app = Flask(__name__)

@app.route("/")
def home():
    return send_from_directory(
        os.path.dirname(os.path.abspath(__file__)),
        "atlas_live_erweitert.html"
    )

@app.route("/health")
def health():
    return jsonify({"status": "online", "app": "ATLAS LIVE"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
