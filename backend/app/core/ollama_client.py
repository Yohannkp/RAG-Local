import base64
import json
import re
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


PHOTO_DESCRIPTION_PROMPT = (
    "Analyse cette image pour qu'on puisse la retrouver plus tard avec une "
    "question en français. Réponds UNIQUEMENT avec ces lignes, sans introduction :\n"
    "Type : photo, capture d'écran, document scanné, schéma, illustration ou logo\n"
    "Lieu ou scène : plage, mer, montagne, ville, rue, intérieur, salle, campagne, "
    "forêt, désert… ou « inconnu » si ce n'est pas visible\n"
    "Éléments visibles : objets, éléments naturels, bâtiments, véhicules, animaux\n"
    "Personnes : nombre, âge apparent, ce qu'elles font, ou « aucune »\n"
    "Activité : ce qui se passe\n"
    "Ambiance : moment de la journée, météo, couleurs dominantes\n"
    "Texte visible : transcris fidèlement le texte lisible, ou « aucun »\n"
    "Mots-clés : 8 à 12 mots ou synonymes en français (ex. plage, mer, sable, océan, vacances, soleil)\n"
    "Sois factuel : ne décris que ce que tu vois vraiment, n'invente ni lieu ni personne."
)

_THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def strip_thinking(text: str) -> str:
    return _THINK_RE.sub("", text).strip()


class OllamaClient:
    def __init__(self, base_url: str = settings.ollama_base_url):
        self._base_url = base_url.rstrip("/")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self._base_url}/api/embed",
                json={
                    "model": settings.embed_model,
                    "input": texts,
                    "keep_alive": settings.embed_keep_alive,
                },
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
            "keep_alive": settings.chat_keep_alive,
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

    async def describe_image(self, image_bytes: bytes, prompt: str | None = None) -> str:
        payload = {
            "model": settings.vision_model,
            "think": False,
            "messages": [
                {
                    "role": "user",
                    "content": prompt or IMAGE_DESCRIPTION_PROMPT,
                    "images": [base64.b64encode(image_bytes).decode("ascii")],
                }
            ],
            "stream": False,
            "keep_alive": settings.vision_keep_alive,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            return strip_thinking(resp.json()["message"]["content"])

    async def chat_once(
        self, messages: list[dict], json_format: bool = False, num_ctx: int = 4096
    ) -> str:
        """Réponse complète, sans raisonnement affiché (jugement, extraction)."""
        payload: dict = {
            "model": settings.chat_model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {"num_ctx": num_ctx, "temperature": 0},
            "keep_alive": settings.chat_keep_alive,
        }
        if json_format:
            payload["format"] = "json"
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            return strip_thinking(resp.json()["message"]["content"])

    async def describe_text(self, text: str, filename: str) -> str:
        prompt = (
            "Résume précisément le contenu utile de ce fichier en français en "
            "quelques phrases. Mentionne les sujets, personnes, lieux, dates, "
            "objets ou informations qui aideront à le retrouver par une question "
            "en langage naturel. N'invente rien. Fichier: "
            f"{filename}\n\nContenu:\n{text[:12000]}"
        )
        result = ""
        async for chunk in self.chat_stream(
            [{"role": "user", "content": prompt}], num_ctx=4096
        ):
            result += chunk
        return result.strip()

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
