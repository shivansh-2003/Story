// CI guard for the design spec's §16 budget: "three must never appear in
// any chunk reachable from a protected route." three.js only gets pulled in
// by features/landing/HeroCanvas.tsx (dynamically imported, lazy, public
// route only) — so any built chunk containing three.js internals must be
// that chunk. "WebGLRenderer" is a string three.js embeds in a runtime
// error message; it survives minification unlike class/function names.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const assetsDir = join(import.meta.dirname, "..", "dist", "assets");
const files = readdirSync(assetsDir).filter((f) => f.endsWith(".js"));

const offenders = files.filter((f) => {
  if (f.startsWith("HeroCanvas")) return false;
  return readFileSync(join(assetsDir, f), "utf8").includes("WebGLRenderer");
});

if (offenders.length > 0) {
  console.error("three.js leaked into a chunk outside the landing hero:");
  for (const f of offenders) console.error(`  - ${f}`);
  process.exit(1);
}

console.log(`Bundle check passed — three.js is isolated to the HeroCanvas chunk (${files.length} chunks scanned).`);
