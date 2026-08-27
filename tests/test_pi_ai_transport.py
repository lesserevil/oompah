"""Tests for the optional Pi AI JSONL transport."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from oompah.pi_ai_transport import PI_AI_PROTOCOL, PiAiTransport, PiAiTransportError


def _bridge(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "bridge.mjs"
    path.write_text(body, encoding="utf-8")
    return path


def test_missing_bridge_fails_before_provider_contact(tmp_path):
    contacted = []
    transport = PiAiTransport(
        workspace_path=str(tmp_path), provider="faux", model="faux",
        bridge_path=tmp_path / "missing.mjs",
        before_transport_contact=lambda: contacted.append(True) or None,
    )
    with pytest.raises(PiAiTransportError, match="bridge is unavailable"):
        asyncio.run(transport.start())
    assert contacted == []


def test_bridge_initializes_and_streams_one_completion(tmp_path):
    bridge = _bridge(tmp_path, r'''import readline from "node:readline";
const rl = readline.createInterface({input: process.stdin, crlfDelay: Infinity});
rl.on("line", line => {
  const msg = JSON.parse(line);
  if (msg.type === "initialize") process.stdout.write(JSON.stringify({type:"ready", id:msg.id, protocol:msg.protocol}) + "\n");
  else if (msg.type === "complete") {
    process.stdout.write(JSON.stringify({type:"provider_start", id:msg.id}) + "\n");
    process.stdout.write(JSON.stringify({type:"text_delta", id:msg.id, delta:"hello"}) + "\n");
    process.stdout.write(JSON.stringify({type:"done", id:msg.id, message:{role:"assistant", content:[{type:"text", text:"hello"}], usage:{input:2,output:1,totalTokens:3,cost:{total:0.01}}, stopReason:"stop"}}) + "\n");
  } else if (msg.type === "shutdown") process.exit(0);
});
''')
    contacted = []

    async def run():
        transport = PiAiTransport(
            workspace_path=str(tmp_path), provider="faux", model="faux",
            bridge_path=bridge,
            before_transport_contact=lambda: contacted.append(True) or None,
        )
        try:
            events = [event async for event in transport.complete(
                system_prompt="system",
                messages=[{"role": "user", "content": "hi", "timestamp": 1}],
                tools=[], max_tokens=100,
            )]
            assert [event["type"] for event in events] == ["provider_start", "text_delta", "done"]
            assert events[-1]["message"]["usage"]["totalTokens"] == 3
            assert transport.transport_contacted is True
        finally:
            await transport.close()

    asyncio.run(run())
    assert contacted == [True]


def test_transport_denial_prevents_complete_frame(tmp_path):
    capture = tmp_path / "frames.jsonl"
    bridge = _bridge(tmp_path, f'''import fs from "node:fs";
import readline from "node:readline";
const rl = readline.createInterface({{input: process.stdin, crlfDelay: Infinity}});
rl.on("line", line => {{
  const msg = JSON.parse(line); fs.appendFileSync({json.dumps(str(capture))}, JSON.stringify(msg) + "\\n");
  if (msg.type === "initialize") process.stdout.write(JSON.stringify({{type:"ready", id:msg.id, protocol:msg.protocol}}) + "\\n");
  if (msg.type === "shutdown") process.exit(0);
}});
''')

    async def run():
        transport = PiAiTransport(
            workspace_path=str(tmp_path), provider="faux", model="faux",
            bridge_path=bridge,
            before_transport_contact=lambda: "authority revoked",
        )
        try:
            with pytest.raises(PiAiTransportError, match="authority revoked"):
                async for _ in transport.complete(system_prompt="", messages=[], tools=[], max_tokens=10):
                    pass
        finally:
            await transport.close()

    asyncio.run(run())
    frames = [json.loads(line) for line in capture.read_text().splitlines()]
    assert [frame["type"] for frame in frames] == ["initialize", "shutdown"]


def test_real_bridge_declares_framework_only_dependency():
    root = Path(__file__).resolve().parents[1] / "bridge" / "pi-ai"
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    source = (root / "src" / "main.mjs").read_text(encoding="utf-8")
    assert package["dependencies"] == {"@earendil-works/pi-ai": "0.84.3"}
    assert "pi-coding-agent" not in source
    assert "pi-agent-core" not in source
    assert PI_AI_PROTOCOL in source
