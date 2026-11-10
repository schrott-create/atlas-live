import fs from "node:fs";
import vm from "node:vm";

const path = new URL("../atlas_live_erweitert.html", import.meta.url);
const html = fs.readFileSync(path, "utf8");
const scriptTags = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)];
let checkedScripts = 0;

for (const [, attrs, source] of scriptTags) {
  if (/application\/ld\+json/i.test(attrs)) {
    JSON.parse(source);
    continue;
  }
  if (!source.trim()) continue;
  new vm.Script(source, { filename: "atlas_live_erweitert.html:inline-script" });
  checkedScripts++;
}

const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
const idSet = new Set(ids);
const duplicates = ids.filter((id, index) => ids.indexOf(id) !== index);
const references = [...html.matchAll(/\$\(['"]([^'"]+)['"]\)/g)].map((match) => match[1]);
const missing = [...new Set(references.filter((id) => !idSet.has(id)))];

if (duplicates.length) throw new Error("Doppelte HTML-IDs: " + [...new Set(duplicates)].join(", "));
if (missing.length) throw new Error("Nicht vorhandene DOM-IDs: " + missing.join(", "));

const sharedLine = html.split("\n").find((line) => line.includes("const match=window.location.hash"));
const regexLiteral = sharedLine?.match(/\.match\((\/.*\/)\);/)?.[1];
if (!regexLiteral) throw new Error("Share-Link-Prüfung konnte nicht gefunden werden.");
const shareRegex = new Function("return " + regexLiteral)();
if (!shareRegex.test("#map=44.18,-75.93,9")) {
  throw new Error("Geteilte Kartenlinks werden nicht korrekt erkannt.");
}

function readArray(name) {
  const prefix = "const " + name + "=";
  const start = html.indexOf(prefix);
  if (start < 0) throw new Error("Datenliste fehlt: " + name);
  const valueStart = start + prefix.length;
  const end = html.indexOf(";\n", valueStart);
  if (end < 0) throw new Error("Datenliste ist nicht sauber abgeschlossen: " + name);
  return new Function("return (" + html.slice(valueStart, end) + ")")();
}

const sourceLists = ["citySources", "regionalSources", "worldSources"].map(readArray);
let cameraCount = 0;
for (const list of sourceLists) {
  cameraCount += list.length;
  for (const camera of list) {
    if (!camera.name || !/^https:\/\//.test(camera.url || "")) {
      throw new Error("Kameraquelle ohne Namen oder HTTPS-Link: " + (camera.name || "unbekannt"));
    }
    if (!Number.isFinite(Number(camera.lat)) || !Number.isFinite(Number(camera.lon)) ||
        Math.abs(Number(camera.lat)) > 90 || Math.abs(Number(camera.lon)) > 180) {
      throw new Error("Ungültige Koordinaten: " + camera.name);
    }
    if (camera.embedUrl && !/^https:\/\//.test(camera.embedUrl)) {
      throw new Error("Unsicherer oder ungültiger Player-Link: " + camera.name);
    }
    if (camera.imageUrl && !/^https:\/\//.test(camera.imageUrl)) {
      throw new Error("Unsicherer oder ungültiger Bild-Link: " + camera.name);
    }
  }
}


// Every clickable city must have a geographic rule, and every directory city must be reachable.
const cityRuleNames = [...html.matchAll(/^\s*'([^']+)':\{aliases:/gm)].map(match => match[1]);
const cityRuleSet = new Set(cityRuleNames);
const cityButtons = [...html.matchAll(/data-global-city="([^"]+)"/g)].map(match => match[1]);
const missingRules = cityButtons.filter(city => !cityRuleSet.has(city));
if (missingRules.length) throw new Error("Städte ohne geografische Suchregel: " + missingRules.join(", "));
if (cityRuleSet.size !== cityRuleNames.length) throw new Error("Doppelte Stadtschlüssel gefunden.");
const directoryStart = html.indexOf("const GLOBAL_CITY_DIRECTORY=");
const directoryEnd = html.indexOf(";\nfunction organizeGlobalCityPicker", directoryStart);
if (directoryStart < 0 || directoryEnd < 0) throw new Error("Kontinent-/Länderverzeichnis fehlt.");
const directory = JSON.parse(html.slice(directoryStart + "const GLOBAL_CITY_DIRECTORY=".length, directoryEnd));
const directoryCities = directory.flatMap(entry => entry[3]);
const unknownCities = directoryCities.filter(city => !cityRuleSet.has(city));
if (unknownCities.length) throw new Error("Orte im Länderverzeichnis ohne Ortsregel: " + unknownCities.join(", "));
if (new Set(directoryCities).size !== directoryCities.length) throw new Error("Doppelte Orte im Länderverzeichnis.");
if (!html.includes("selectedGlobalCity||!map.hasLayer(pointLayers.webcams)")) {
  throw new Error("Kartenschwenken darf aktive Stadtsuchen nicht überschreiben.");
}
if (!html.includes("bbox,limit:'500'") || !html.includes("filterGlobalCityRows([...collected.values()],city)")) {
  throw new Error("Geografische Stadtsuche oder Koordinatenfilter fehlt.");
}

for (const id of ["map", "search", "windyLoad", "openWall", "randomCamera", "shareAtlas", "camviewer", "radioSearch"]) {
  if (!idSet.has(id)) throw new Error("Wichtige UI-Komponente fehlt: " + id);
}

if (html.includes("roadmapOverlay") || html.includes("openRoadmap") || html.includes("roadmapPrevious") || html.includes("roadmapNew")) throw new Error("Entfernter 80-Ideen-Tab ist noch im Frontend vorhanden.");
if (!html.includes("radioMarkers") || !html.includes("geo_lat") || !html.includes("radioSearch")) throw new Error("Radio-Kartenpunkte oder Suchfunktion fehlen.");
if (!html.includes("getFintrafficCameraSources") || !html.includes("weathercam.digitraffic.fi")) throw new Error("Fintraffic-Kameras oder Bildaktualisierung fehlen.");
if (!html.includes("basemaps.cartocdn.com/dark_all")) throw new Error("Dunkle Kartenkacheln fehlen.");
if (!html.includes("basemaps.cartocdn.com/rastertiles/voyager")) throw new Error("Neue Kartenbasis fehlt.");
if (!html.includes('data-layer="radio"') || !html.includes('data-layer="webcams"')) throw new Error("Seitliche Kartenebenen fehlen.");
if (!html.includes("params.set('limit','200')")) throw new Error("Radio-Kartenpunkte werden nicht mit erweitertem Limit geladen.");
if (html.includes("stateCamsOverlay") || html.includes("maritimeOverlay")) throw new Error("Externe Kamera-Verteiler-Overlays sind noch vorhanden.");
if (html.includes("H_EbNSqfoso")) throw new Error("Veralteter Alexandria-Bay-Stream ist noch eingetragen.");
console.log("Frontend-Prüfung OK: " + checkedScripts + " JavaScript-Block/Blöcke, JSON-LD, " +
  ids.length + " IDs, DOM-Referenzen, Share-Link, " + cameraCount + " Kameraquellen und Radio-Kartenpunkte.");
