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

for (const id of ["map", "search", "windyLoad", "openWall", "randomCamera", "openRoadmap", "shareAtlas", "camviewer"]) {
  if (!idSet.has(id)) throw new Error("Wichtige UI-Komponente fehlt: " + id);
}

console.log("Frontend-Prüfung OK: " + checkedScripts + " JavaScript-Block/Blöcke, JSON-LD, " + ids.length + " IDs, DOM-Referenzen und Karten-Share-Link.");
