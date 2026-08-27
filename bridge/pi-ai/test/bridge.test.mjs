import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

const source = await readFile(new URL("../src/main.mjs", import.meta.url), "utf8");
const pkg = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));

test("bridge depends only on pi-ai framework package", () => {
  assert.deepEqual(pkg.dependencies, { "@earendil-works/pi-ai": "0.84.3" });
  assert.doesNotMatch(source, /pi-coding-agent|pi-agent-core/);
});

test("bridge exposes bounded versioned JSONL commands", () => {
  assert.match(source, /oompah-pi-ai-v1/);
  assert.match(source, /MAX_FRAME_BYTES/);
  for (const command of ["initialize", "complete", "abort", "shutdown"]) assert.match(source, new RegExp(`command\\.type === \\"${command}\\"`));
});

test("bridge accepts only supplied tool schemas", () => {
  assert.match(source, /command\.tools\.map\(normalizeTool\)/);
  assert.doesNotMatch(source, /createBashTool|createReadTool|createAgentSession/);
});
