"""Deterministic OpenAI-compatible stub for exercising the live CaMeL harness.

It answers every chat completion with the one line of CaMeL code that the
harness's prompt asks for ("Append exactly the following text to cloud-drive
file ID <id>: <content>").  It contains no model; its purpose is to test the
pipeline wiring, the policy seam and the grader without a GPU or API key.
Records produced with it are tagged ``model_kind = "deterministic_stub"``.

Usage:  python tests/fake_privileged_llm_server.py --port 8765
Then:   python -m vac_study.live_camel_study --base-url http://127.0.0.1:8765/v1 \
            --model stub --model-kind deterministic_stub --out results/live/harness_dry_run.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PATTERN = re.compile(r"file ID (\S+): (.*)$", re.S)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        text = ""
        for message in reversed(payload.get("messages", [])):
            if message.get("role") == "user":
                content = message.get("content")
                if isinstance(content, list):
                    content = " ".join(part.get("text", "") for part in content if isinstance(part, dict))
                text = content or ""
                break
        match = PATTERN.search(text)
        if match:
            file_id, content = match.group(1).strip(), match.group(2).strip()
            code = f'```python\nappend_to_file(file_id={json.dumps(file_id)}, content={json.dumps(content)})\n```'
        else:
            code = "```python\nprint('no instruction recognised')\n```"
        body = {
            "id": "chatcmpl-stub", "object": "chat.completion", "created": int(time.time()),
            "model": payload.get("model", "stub"),
            "choices": [{"index": 0, "message": {"role": "assistant", "content": code}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8765)
    a = p.parse_args()
    print(f"stub privileged-LLM server on http://127.0.0.1:{a.port}/v1 (deterministic, not a model)", flush=True)
    HTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
