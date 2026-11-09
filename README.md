# ATLAS LIVE

**Kostenloser Explorer für öffentliche Live-Webcams** – Städte, Straßen, Häfen, Küsten, Natur, Wetter, Flughäfen und öffentliche Bordkameras.

ATLAS LIVE verbindet eine interaktive Weltkarte mit einer durchsuchbaren Sammlung öffentlicher Kameraquellen. Das Projekt ist bewusst so aufgebaut, dass es ohne Benutzerkonto genutzt werden kann.

## Was die App kann

- Interaktive Karte mit Orts- und Straßensuche
- Öffentliche Kameraquellen aus verschiedenen Ländern
- Regionale Kameras rund um La Fargeville und die Thousand Islands
- Windy-Webcams-Integration mit optionalem persönlichem API-Key
- Autobahn-Webcams und Fintraffic-Wetterkameras
- Öffentliche Hafen-, Küsten- und Schiffs-Webcam-Verzeichnisse
- Kamera-Favoriten und persönliche Ordner (lokal im Browser)
- Zufallskamera
- Kamera-Live-Wall für Quellen mit bestätigtem Einbettungslink
- Teilbare Kartenansicht
- Roadmap mit 30 bisherigen und 50 zusätzlichen Ausbauideen
- Dynamische `robots.txt` und `sitemap.xml`

## Nutzung

Die Anwendung wird über die öffentliche Website geöffnet. Die Karten- und Kameraliste lädt öffentliche Datenquellen. Einige Anbieter erlauben keine Einbettung; diese Quellen werden direkt beim Betreiber geöffnet.

Der optionale Windy-Webcams-API-Key wird nur im aktuellen Browser-Tab verwendet und nicht in diesem Repository gespeichert. Ohne Key kann die offizielle Windy-Webcam-Karte geöffnet werden.

Favoriten und eigene Ordner bleiben derzeit lokal im jeweiligen Browser. Es gibt keine geräteübergreifende Synchronisierung und kein Benutzerkonto.

## Kostenloser Betrieb

Das Projekt ist für einen kostenlosen Hobbybetrieb ausgelegt. Der Render-Free-Webdienst kann bei Inaktivität einschlafen und beim ersten Aufruf eine kurze Startzeit benötigen. Externe Kameraanbieter, Kartenserver und APIs haben eigene Verfügbarkeits- und Nutzungsgrenzen. Ein kostenloser Betrieb ist daher nicht mit einer garantierten 24/7-Verfügbarkeit gleichzusetzen.

## Entwicklung und Quellen

- Kartenbibliothek: Leaflet
- Kartendaten: © OpenStreetMap-Mitwirkende
- Geocoding: Nominatim / OpenStreetMap
- Weitere Daten: jeweils beim Kameraeintrag genannte öffentliche Anbieter

Bitte die Nutzungsbedingungen und Bildrechte der jeweiligen Anbieter beachten. ATLAS LIVE ist ein unabhängiger Webcam-Explorer und nicht mit Windy, Reedereien oder den aufgeführten Kamerabetreibern verbunden.

## Roadmap

Die Roadmap in der App zeigt den aktuellen Funktionsstand und weitere geplante Ideen. Ein Roadmap-Eintrag ist nicht automatisch eine bereits implementierte Funktion. Neue Kameraquellen werden nur dann als direkte Live-Player dargestellt, wenn dafür ein geeigneter öffentlicher Einbettungslink vorhanden ist.

## Automatische Prüfungen

Bei jedem Push und Pull Request führt GitHub Actions diese Prüfungen aus:

- Python-Syntaxprüfung
- Backend-Tests für Startseite, Health-Check, SEO-Endpunkte und API-Proxys
- JavaScript-Syntaxprüfung und JSON-LD-Validierung
- Prüfung aller festen DOM-Referenzen
- Prüfung von Kamera-Links, Koordinaten und Player-Links
- Kontrolle der 30 bisherigen und 50 neuen Roadmap-Einträge

Lokal ausführbar:

```bash
python -m compileall -q atlas_server.py tests
python -m unittest discover -s tests -v
node scripts/check_frontend.mjs
```

Die automatischen Prüfungen ersetzen keinen echten Browser-Test mit externen Kameraanbietern. Ob ein Anbieter einen Player zulässt und ob ein Feed gerade online ist, hängt weiterhin vom jeweiligen Betreiber ab.
