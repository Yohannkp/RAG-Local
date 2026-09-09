import base64
import json
from collections.abc import AsyncIterator

import httpx

from app.config import settings

IMAGE_DESCRIPTION_PROMPT = (
    "Décris precisément le contenu de cette image, en français. "
    "Si elle contient du texte (capture d'écran, tableau, document scanné), "
    "transcris-le fidèlement en entier. Si c'est un graphique, un diagramme ou "
    "une photo, décris les informations factuelles qu'elle montre (données, "
    "tendances, éléments visibles). Sois factuel et concis, sans commentaire "
    "sur la mise en forme."
)


class OllamaClient:
    def __init__(self, base_url: str = settings.ollama_base_url):
        self._base_url = base_url.rstrip("/")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self._base_url}/api/embed",
                json={"model": settings.embed_model, "input": texts},
            )
            resp.raise_for_status()
            return resp.json()["embeddings"]

    async def chat_stream(
        self, messages: list[dict], num_ctx: int = settings.num_ctx
    ) -> AsyncIterator[str]:
        payload = {
            "model": settings.chat_model,
            "messages": messages,
            "stream": True,
            "options": {"num_ctx": num_ctx},
        }
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST", f"{self._base_url}/api/chat", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("done"):
                        break
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk

    async def describe_image(self, image_bytes: bytes) -> str:
        payload = {
            "model": settings.vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": IMAGE_DESCRIPTION_PROMPT,
                    "images": [base64.b64encode(image_bytes).decode("ascii")],
                }
            ],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()

    async def is_reachable(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def has_required_models(self) -> dict[str, bool]:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{self._base_url}/api/tags")
            resp.raise_for_status()
            names = {m["name"] for m in resp.json().get("models", [])}

        def _present(model: str) -> bool:
            return any(n == model or n.startswith(f"{model}:") for n in names)

        return {
            settings.chat_model: _present(settings.chat_model),
            settings.embed_model: _present(settings.embed_model),
            settings.vision_model: _present(settings.vision_model),
        }


ollama_client = OllamaClient()
