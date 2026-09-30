import hashlib
import math
import re
from pathlib import Path

import pytest
from PIL import Image

from app.config import settings
from app.core.ollama_client import ollama_client
from app.services import local_chat, local_search

DIM = 64


def _vec(text: str) -> list[float]:
    v = [0.0] * DIM
    for w in re.findall(r"[a-zà-ÿ]{3,}", text.lower()):
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


DESCRIPTIONS: dict[int, str] = {}


@pytest.fixture(autouse=True)
def fake_ollama(monkeypatch, tmp_path):
    async def embed(texts):
        return [_vec(t) for t in texts]

    async def describe(image_bytes, prompt=None):
        img = Image.open(__import__("io").BytesIO(image_bytes)).convert("RGB")
        r, g, b = img.getpixel((5, 5))
        if b > 200:
            return "Type : photo. Lieu : plage de sable avec la mer et des vagues. Mots-clés : plage, mer, sable."
        return "Type : photo. Lieu : salon d'un appartement avec un canapé. Mots-clés : salon, canapé."

    async def chat_once(messages, json_format=False, num_ctx=4096):
        text = messages[-1]["content"]
        picked = [int(m.group(1)) for m in re.finditer(r"\[(\d+)\][^\n]*\n[^\n]*(plage|sable)", text, re.I)]
        return '{"correspond": %s}' % picked

    async def chat_stream(messages):
        yield "réponse"

    monkeypatch.setattr(ollama_client, "embed", embed)
    monkeypatch.setattr(ollama_client, "describe_image", describe)
    monkeypatch.setattr(ollama_client, "chat_once", chat_once)
    monkeypatch.setattr(ollama_client, "chat_stream", chat_stream)
    monkeypatch.setattr(settings, "local_min_image_bytes", 0)
    monkeypatch.setattr(settings, "local_min_image_side", 0)
    monkeypatch.setattr(settings, "local_index_manifest_path", tmp_path / "manifest.json")
    local_search.reset_local_collection() if hasattr(local_search, "reset_local_collection") else None
    local_search._last_scan_started = 0.0
    local_search._index_task = None


def _photo(path: Path, color):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (300, 300), color).save(path)


async def _run(root: Path, query: str) -> str:
    out = ""
    async for kind, payload in local_chat.stream_local_answer(query, [], root_path=str(root)):
        if kind == "token":
            out += payload
    return out


@pytest.mark.asyncio
async def test_finds_beach_photos_and_lists_them(tmp_path):
    root = tmp_path / "home"
    _photo(root / "Pictures" / "vacances" / "IMG_1.jpg", (10, 10, 250))
    _photo(root / "Pictures" / "salon.jpg", (200, 50, 50))
    (root / "Documents").mkdir()
    (root / "Documents" / "notes.txt").write_text("liste de courses", encoding="utf-8")
    await local_search.index_local_files(str(root))
    answer = await _run(root, "trouve moi les photos que j'ai prises à la plage")
    assert "IMG_1.jpg" in answer
    assert "salon.jpg" not in answer


@pytest.mark.asyncio
async def test_absence_is_stated_with_full_coverage(tmp_path):
    root = tmp_path / "home"
    _photo(root / "Pictures" / "salon.jpg", (200, 50, 50))
    await local_search.index_local_files(str(root))
    answer = await _run(root, "trouve moi les photos de neige à la montagne")
    assert "aucun fichier" in answer.lower()
    assert "complète" in answer
    assert "1 image(s) sur 1" in answer


@pytest.mark.asyncio
async def test_absence_is_not_claimed_when_index_incomplete():
    stats = {"complete": False, "running": True, "images_pending": 40, "documents_pending": 0,
             "truncated": False, "failed": 0, "images_indexed": 10, "images_total": 50,
             "documents_indexed": 3, "documents_total": 3, "skipped_small_images": 0}
    msg = local_chat.absence_message(stats, 0)
    assert "ne peux pas affirmer" in msg
    assert "40 image(s)" in msg
