#!/usr/bin/env python3
"""
Sovereign GGUF Model Server
OpenAI-compatible inference server backed by llama-cpp-python.
Port 8300 | No auth | ~/.config/amallo/gguf_catalogue.json
"""

import asyncio
import json
import os
import sys
import time
import uuid
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

# ─── Paths ────────────────────────────────────────────────────────────────────
MODELS_DIR = Path.home() / "models" / "gguf"
CATALOGUE_PATH = Path.home() / ".config" / "amallo" / "gguf_catalogue.json"
PORT = 8300

# ─── Globals ──────────────────────────────────────────────────────────────────
_llm = None          # current loaded Llama instance
_loaded_model = None # name of currently loaded model
_llm_lock = threading.Lock()


# ─── Catalogue helpers ────────────────────────────────────────────────────────

def load_catalogue() -> Dict[str, Any]:
    if CATALOGUE_PATH.exists():
        try:
            return json.loads(CATALOGUE_PATH.read_text())
        except Exception:
            pass
    return {}


def save_catalogue(cat: Dict[str, Any]) -> None:
    CATALOGUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOGUE_PATH.write_text(json.dumps(cat, indent=2))


def catalogue_entry(name: str, path: str, pull_source: str = "") -> Dict[str, Any]:
    size = Path(path).stat().st_size if Path(path).exists() else 0
    return {
        "name": name,
        "path": str(path),
        "size": size,
        "size_human": _human_size(size),
        "last_used": None,
        "pull_source": pull_source,
        "added_at": datetime.now(timezone.utc).isoformat(),
    }


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


# ─── Model scanning ───────────────────────────────────────────────────────────

def scan_and_populate() -> Dict[str, Any]:
    """Scan ~/models/gguf/ and add any .gguf files not yet in catalogue."""
    cat = load_catalogue()
    found = list(MODELS_DIR.rglob("*.gguf")) if MODELS_DIR.exists() else []
    added = 0
    for fpath in found:
        name = fpath.name
        if name not in cat:
            cat[name] = catalogue_entry(name, str(fpath))
            added += 1
    if added:
        save_catalogue(cat)
    return cat


# ─── Model loading ────────────────────────────────────────────────────────────

def _load_model(model_name: str) -> None:
    global _llm, _loaded_model

    try:
        from llama_cpp import Llama
    except ImportError:
        raise RuntimeError("llama-cpp-python not installed. Run: pip install llama-cpp-python")

    cat = load_catalogue()
    if model_name not in cat:
        # Try fuzzy match (substring)
        matches = [k for k in cat if model_name.lower() in k.lower()]
        if not matches:
            raise ValueError(f"Model '{model_name}' not found in catalogue.")
        model_name = matches[0]

    entry = cat[model_name]
    model_path = Path(entry["path"])
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    with _llm_lock:
        if _loaded_model == model_name and _llm is not None:
            return  # already loaded

        # Unload previous
        if _llm is not None:
            del _llm
            _llm = None
            _loaded_model = None

        print(f"  [gguf] Loading {model_name} …", flush=True)
        _llm = Llama(
            model_path=str(model_path),
            n_ctx=4096,
            n_gpu_layers=-1,   # use GPU if available, else CPU
            verbose=False,
        )
        _loaded_model = model_name

        # Update last_used
        cat[model_name]["last_used"] = datetime.now(timezone.utc).isoformat()
        save_catalogue(cat)
        print(f"  [gguf] {model_name} ready.", flush=True)


# ─── Pydantic models ──────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 512
    top_p: float = 0.95
    stream: bool = False
    stop: Optional[List[str]] = None


class PullRequest(BaseModel):
    model: str = Field(..., description="HuggingFace repo, e.g. bartowski/Phi-4-mini-instruct-GGUF")
    filename: str = Field(..., description="Filename in the repo, e.g. Phi-4-mini-instruct-Q4_K_M.gguf")


# ─── FastAPI app ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    cat = scan_and_populate()
    _print_banner(cat)
    yield
    # Cleanup on shutdown
    global _llm
    if _llm is not None:
        del _llm
        _llm = None


app = FastAPI(
    title="Sovereign GGUF Server",
    version="1.0.0",
    description="OpenAI-compatible local inference via llama-cpp-python",
    lifespan=lifespan,
)


def _print_banner(cat: Dict[str, Any]) -> None:
    width = 60
    print("╔" + "═" * width + "╗")
    print("║" + " SOVEREIGN GGUF SERVER".center(width) + "║")
    print("║" + f" Port {PORT} | llama-cpp-python backend".center(width) + "║")
    print("╠" + "═" * width + "╣")
    if cat:
        print("║" + " Available Models:".ljust(width) + "║")
        for name, entry in cat.items():
            line = f"   • {name}  ({entry.get('size_human','?')})"
            print("║" + line.ljust(width) + "║")
    else:
        print("║" + "  No models found. Use POST /gguf/pull to download.".ljust(width) + "║")
    print("╠" + "═" * width + "╣")
    print("║" + " Endpoints:".ljust(width) + "║")
    endpoints = [
        "  GET  /health",
        "  GET  /v1/models",
        "  POST /v1/chat/completions",
        "  POST /gguf/pull",
        "  GET  /gguf/catalogue",
        "  DELETE /gguf/unload",
    ]
    for ep in endpoints:
        print("║" + ep.ljust(width) + "║")
    print("╚" + "═" * width + "╝")
    sys.stdout.flush()


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "loaded_model": _loaded_model,
        "catalogue_size": len(load_catalogue()),
        "models_dir": str(MODELS_DIR),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── /v1/models ───────────────────────────────────────────────────────────────

@app.get("/v1/models")
async def list_models():
    cat = load_catalogue()
    data = [
        {
            "id": name,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "local",
            "size": entry.get("size", 0),
            "size_human": entry.get("size_human", "?"),
            "path": entry.get("path", ""),
            "last_used": entry.get("last_used"),
        }
        for name, entry in cat.items()
    ]
    return {"object": "list", "data": data}


# ─── /v1/chat/completions ─────────────────────────────────────────────────────

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    # Load model (swap if needed) in thread pool to avoid blocking event loop
    try:
        await asyncio.get_event_loop().run_in_executor(None, _load_model, req.model)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    if req.stream:
        return StreamingResponse(
            _stream_chat(messages, req),
            media_type="text/event-stream",
        )

    # Blocking inference — run in thread pool
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _llm.create_chat_completion(
                messages=messages,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
                top_p=req.top_p,
                stop=req.stop,
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {e}")

    # Normalise to OpenAI schema
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    choice = result["choices"][0]
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": _loaded_model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": choice["message"]["content"],
                },
                "finish_reason": choice.get("finish_reason", "stop"),
            }
        ],
        "usage": result.get("usage", {}),
    }


async def _stream_chat(messages, req: ChatCompletionRequest):
    """Server-sent events streaming generator."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _run_inference():
        try:
            for chunk in _llm.create_chat_completion(
                messages=messages,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
                top_p=req.top_p,
                stop=req.stop,
                stream=True,
            ):
                asyncio.run_coroutine_threadsafe(queue.put(chunk), loop)
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)

    thread = threading.Thread(target=_run_inference, daemon=True)
    thread.start()

    while True:
        chunk = await queue.get()
        if chunk is None:
            break
        delta = chunk["choices"][0].get("delta", {})
        finish_reason = chunk["choices"][0].get("finish_reason")
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": _loaded_model,
            "choices": [
                {
                    "index": 0,
                    "delta": delta,
                    "finish_reason": finish_reason,
                }
            ],
        }
        yield f"data: {json.dumps(payload)}\n\n"

    yield "data: [DONE]\n\n"


# ─── /gguf/pull ───────────────────────────────────────────────────────────────

@app.post("/gguf/pull")
async def pull_model(req: PullRequest, background_tasks: BackgroundTasks):
    """Download a GGUF file from HuggingFace and register it in the catalogue."""
    dest = MODELS_DIR / req.filename
    if dest.exists():
        cat = load_catalogue()
        if req.filename in cat:
            return {"status": "already_exists", "model": req.filename, "path": str(dest)}

    # Kick off download in background so client gets immediate response
    background_tasks.add_task(_pull_worker, req.model, req.filename, dest)
    return {
        "status": "downloading",
        "model": req.filename,
        "source": f"https://huggingface.co/{req.model}/resolve/main/{req.filename}",
        "dest": str(dest),
        "message": "Download started. Poll GET /gguf/catalogue to track completion.",
    }


def _pull_worker(repo: str, filename: str, dest: Path) -> None:
    """Download worker — uses huggingface_hub for resumable chunked download."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("[gguf/pull] huggingface-hub not installed, falling back to httpx.", flush=True)
        _pull_httpx(repo, filename, dest)
        return

    print(f"[gguf/pull] Downloading {repo}/{filename} …", flush=True)
    try:
        local_path = hf_hub_download(
            repo_id=repo,
            filename=filename,
            local_dir=str(MODELS_DIR),
            local_dir_use_symlinks=False,
        )
        # hf_hub_download may put file in a sub-dir; copy to flat MODELS_DIR if needed
        local_path = Path(local_path)
        if local_path != dest:
            import shutil
            shutil.move(str(local_path), str(dest))

        cat = load_catalogue()
        pull_source = f"https://huggingface.co/{repo}/resolve/main/{filename}"
        cat[filename] = catalogue_entry(filename, str(dest), pull_source)
        save_catalogue(cat)
        print(f"[gguf/pull] ✓ {filename} saved to {dest}", flush=True)
    except Exception as e:
        print(f"[gguf/pull] ERROR: {e}", flush=True)


def _pull_httpx(repo: str, filename: str, dest: Path) -> None:
    """Fallback raw HTTPS download."""
    url = f"https://huggingface.co/{repo}/resolve/main/{filename}"
    print(f"[gguf/pull] GET {url}", flush=True)
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=None) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)
        cat = load_catalogue()
        cat[filename] = catalogue_entry(filename, str(dest), url)
        save_catalogue(cat)
        print(f"[gguf/pull] ✓ {filename} saved.", flush=True)
    except Exception as e:
        print(f"[gguf/pull] ERROR: {e}", flush=True)


# ─── /gguf/catalogue ─────────────────────────────────────────────────────────

@app.get("/gguf/catalogue")
async def get_catalogue():
    cat = load_catalogue()
    return {
        "catalogue": cat,
        "total": len(cat),
        "models_dir": str(MODELS_DIR),
        "catalogue_path": str(CATALOGUE_PATH),
        "loaded_model": _loaded_model,
    }


# ─── /gguf/unload ─────────────────────────────────────────────────────────────

@app.delete("/gguf/unload")
async def unload_model():
    global _llm, _loaded_model
    with _llm_lock:
        if _llm is None:
            return {"status": "no_model_loaded"}
        name = _loaded_model
        del _llm
        _llm = None
        _loaded_model = None
    return {"status": "unloaded", "model": name}


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "gguf_server:app",
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        access_log=True,
    )
