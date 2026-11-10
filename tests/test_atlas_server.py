import unittest
from unittest.mock import patch
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import atlas_server


class FakeResponse:
    def __init__(self, payload=None, content=b"{}", status_code=200, headers=None):
        self._payload = payload or {}
        self.content = content
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "application/json"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise atlas_server.requests.HTTPError("upstream error")

    def json(self):
        return self._payload


class AtlasServerTests(unittest.TestCase):
    def setUp(self):
        atlas_server.app.config.update(TESTING=True)
        self.client = atlas_server.app.test_client()
        atlas_server._webcam_cache.update({"created": 0.0, "data": {}})
        atlas_server._radio_cache.clear()

    def test_home_serves_application(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"ATLAS LIVE", response.data)

    def test_security_headers(self):
        response = self.client.get("/")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("microphone=()", response.headers["Permissions-Policy"])

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "online")

    def test_robots_and_sitemap_use_request_host(self):
        robots = self.client.get("/robots.txt", base_url="https://atlas.example")
        sitemap = self.client.get("/sitemap.xml", base_url="https://atlas.example")
        self.assertEqual(robots.status_code, 200)
        self.assertIn(b"Sitemap: https://atlas.example/sitemap.xml", robots.data)
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn(b"https://atlas.example/", sitemap.data)
        self.assertIn("application/xml", sitemap.content_type)

    def test_fintraffic_proxy_returns_upstream_data(self):
        payload = b'{"features":[]}'
        with patch.object(atlas_server.requests, "get", return_value=FakeResponse(content=payload)):
            response = self.client.get("/api/fintraffic/stations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, payload)

    def test_fintraffic_proxy_reports_upstream_failure(self):
        with patch.object(atlas_server.requests, "get", side_effect=atlas_server.requests.Timeout):
            response = self.client.get("/api/fintraffic/stations")
        self.assertEqual(response.status_code, 502)
        self.assertIn("error", response.get_json())

    def test_autobahn_webcam_aggregation_and_cache(self):
        def fake_get(url, **kwargs):
            if url.endswith("/"):
                return FakeResponse({"roads": ["A1", "A2"]})
            if url.endswith("/A1/services/webcam"):
                return FakeResponse({"webcam": [{"title": "Cam 1"}]})
            if url.endswith("/A2/services/webcam"):
                return FakeResponse({"webcam": [{"title": "Cam 2"}]})
            raise AssertionError("Unexpected upstream URL: " + url)

        with patch.object(atlas_server.requests, "get", side_effect=fake_get) as mocked:
            first = self.client.get("/api/autobahn/webcams")
            calls_after_first = mocked.call_count
            second = self.client.get("/api/autobahn/webcams")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()["count"], 2)
        self.assertEqual(second.get_json()["count"], 2)
        self.assertEqual(mocked.call_count, calls_after_first)

    def test_autobahn_webcam_route_rejects_invalid_road(self):
        response = self.client.get("/api/autobahn/../../bad/services/webcam")
        self.assertIn(response.status_code, (400, 404))

    def test_autobahn_webcam_proxy(self):
        payload = b'{"webcam":[]}'
        with patch.object(atlas_server.requests, "get", return_value=FakeResponse(content=payload)):
            response = self.client.get("/api/autobahn/A1/services/webcam")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, payload)

    def test_radio_stations_only_returns_online_https_streams(self):
        payload = [
            {"stationuuid": "12345678-1234-1234-1234-123456789012", "name": "Secure Radio",
             "lastcheckok": 1, "url_resolved": "https://stream.example/radio", "country": "Germany",
             "geo_lat": 52.52, "geo_long": 13.405},
            {"stationuuid": "22345678-1234-1234-1234-123456789012", "name": "Insecure Radio",
             "lastcheckok": 1, "url_resolved": "http://stream.example/radio"},
            {"stationuuid": "32345678-1234-1234-1234-123456789012", "name": "Offline Radio",
             "lastcheckok": 0, "url_resolved": "https://stream.example/offline"},
        ]
        with patch.object(atlas_server.requests, "get", return_value=FakeResponse(payload)):
            response = self.client.get("/api/radio/stations?country=Germany&tag=jazz")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["stations"][0]["name"], "Secure Radio")
        self.assertEqual(data["stations"][0]["geo_lat"], 52.52)
        self.assertEqual(data["stations"][0]["geo_long"], 13.405)

    def test_radio_search_uses_short_cache(self):
        payload = [{"name": "Cached", "lastcheckok": 1, "url_resolved": "https://radio.example/live"}]
        with patch.object(atlas_server.requests, "get", return_value=FakeResponse(payload)) as mocked:
            first = self.client.get("/api/radio/stations?country=Germany")
            second = self.client.get("/api/radio/stations?country=Germany")
            third = self.client.get("/api/radio/stations?country=France")
        self.assertEqual(first.get_json()["count"], 1)
        self.assertEqual(second.get_json()["count"], 1)
        self.assertEqual(third.get_json()["count"], 1)
        self.assertEqual(mocked.call_count, 2)

    def test_radio_rejects_malformed_https_urls(self):
        payload = [{"lastcheckok": 1, "url_resolved": "https://"},
                   {"lastcheckok": 1, "url_resolved": "https://user:pass@radio.example/live"},
                   {"lastcheckok": 1, "url_resolved": "https://radio.example/live"}]
        with patch.object(atlas_server.requests, "get", return_value=FakeResponse(payload)):
            response = self.client.get("/api/radio/stations")
        self.assertEqual(response.get_json()["count"], 1)

    def test_radio_click_rejects_invalid_station_uuid(self):
        response = self.client.get("/api/radio/click/not-a-uuid")
        self.assertEqual(response.status_code, 400)

    def test_radio_click_registers_valid_station(self):
        station_uuid = "12345678-1234-1234-1234-123456789012"
        with patch.object(atlas_server.requests, "get", return_value=FakeResponse({"ok": True})):
            response = self.client.get("/api/radio/click/" + station_uuid)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])


if __name__ == "__main__":
    unittest.main()
