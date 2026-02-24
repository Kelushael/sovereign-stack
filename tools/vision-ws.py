#!/usr/bin/env python3
"""Sovereign WebSocket vision server — port 8201"""

import asyncio
import json
import os
import aiohttp
import websockets

OLLAMA_URL = "http://localhost:11434/api/chat"
KEYS_FILE = "/root/amallo/keys.json"
VISION_MODEL = "glm4:latest"
TEXT_MODEL = "dolphin-mistral:latest"


def load_valid_tokens():
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE) as f:
                data = json.load(f)
            # support list of strings or dict with any shape
            if isinstance(data, list):
                return set(data)
            if isinstance(data, dict):
                # values may be tokens, or keys may be tokens
                tokens = set()
                for k, v in data.items():
                    if isinstance(v, str):
                        tokens.add(v)
                    tokens.add(k)
                return tokens
        except Exception as e:
            print(f"[vision-ws] warning: could not load {KEYS_FILE}: {e}")
    return None  # fallback mode


VALID_TOKENS = load_valid_tokens()


def is_authorized(token: str) -> bool:
    if VALID_TOKENS is not None:
        return token in VALID_TOKENS
    return isinstance(token, str) and token.startswith("SOV-")


async def stream_ollama(ws, model: str, messages: list):
    """Stream tokens from Ollama back over the WebSocket."""
    payload = {"model": model, "messages": messages, "stream": True}
    async with aiohttp.ClientSession() as session:
        async with session.post(OLLAMA_URL, json=payload) as resp:
            if resp.status != 200:
                body = await resp.text()
                await ws.send(json.dumps({"type": "error", "message": f"ollama {resp.status}: {body[:200]}"}))
                return
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = chunk.get("message", {}).get("content", "")
                if content:
                    await ws.send(json.dumps({"type": "token", "content": content}))
                if chunk.get("done"):
                    break
    await ws.send(json.dumps({"type": "done"}))


async def handle_message(ws, raw: str):
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        await ws.send(json.dumps({"type": "error", "message": "invalid JSON"}))
        return

    msg_type = msg.get("type", "")

    if msg_type == "ping":
        await ws.send(json.dumps({"type": "pong"}))
        return

    # Auth required for vision/text
    token = msg.get("token", "")
    if not is_authorized(token):
        await ws.send(json.dumps({"type": "error", "message": "unauthorized"}))
        return

    if msg_type == "vision":
        image_url = msg.get("image", "")
        user_text = msg.get("text", "")
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }]
        await stream_ollama(ws, VISION_MODEL, messages)

    elif msg_type == "text":
        user_text = msg.get("text", "")
        messages = [{"role": "user", "content": user_text}]
        await stream_ollama(ws, TEXT_MODEL, messages)

    else:
        await ws.send(json.dumps({"type": "error", "message": f"unknown type: {msg_type}"}))


async def handler(ws):
    remote = ws.remote_address
    print(f"[vision-ws] connect {remote}")
    try:
        async for raw in ws:
            await handle_message(ws, raw)
    except websockets.exceptions.ConnectionClosedOK:
        pass
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"[vision-ws] connection closed error {remote}: {e}")
    except Exception as e:
        print(f"[vision-ws] error {remote}: {e}")
    finally:
        print(f"[vision-ws] disconnect {remote}")


async def main():
    print("[vision-ws] listening on ws://0.0.0.0:8201")
    if VALID_TOKENS is not None:
        print(f"[vision-ws] loaded {len(VALID_TOKENS)} token(s) from {KEYS_FILE}")
    else:
        print("[vision-ws] fallback auth: accepting any SOV-* token")
    async with websockets.serve(handler, "0.0.0.0", 8201):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
