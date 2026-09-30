"""Recherche sur les fichiers de l'ordinateur.

Objectif : à une question comme « trouve-moi les photos que j'ai prises à la
plage », soit retrouver les fichiers, soit pouvoir affirmer qu'il n'y en a pas
PARCE QUE tout a été analysé. Trois garanties en découlent :

1. Couverture : le scan parcourt d'abord les dossiers personnels (Images,
   Bureau, Documents, Téléchargements…), ignore les dossiers cachés et
   techniques, et ne s'arrête pas à un plafond arbitraire. Ce qui est ignoré
   ou pas encore analysé est compté et rapporté (`get_index_stats`).
2. Description utile : chaque photo est décrite par le modèle de vision avec un
   plan fixe (lieu, éléments, personnes, mots-clés) pensé pour la recherche.
3. Jugement : les candidats (recherche vectorielle + mots-clés) sont vérifiés
   par le modèle de chat ; un fichier qui ne répond pas clairement à la
   demande n'est jamais présenté comme un résultat.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.ollama_client import PHOTO_DESCRIPTION_PROMPT, ollama_client
from app.core.parsing.docx_parser import parse_docx
from app.core.parsing.pdf_parser import parse_pdf
from app.core.vector_store import local_collection, reset_local_collection

SCHEMA_VERSION = 3  # à changer quand le format de l'index change : il est reconstruit

_TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".log", ".yaml", ".yml", ".ini", ".cfg",
    ".toml", ".xml", ".html", ".htm", ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".cs", ".sql", ".bash", ".sh", ".ps1", ".tex", ".rst",
}
_SUPPORTED_TEXT_EXTENSIONS = _TEXT_EXTENSIONS | {".pdf", ".docx"}
_SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif"}
_IMAGE_EXT_LIST = sorted(ext.lstrip(".") for ext in _SUPPORTED_IMAGE_EXTENSIONS)

# Dossiers personnels analysés en premier (noms en minuscules, préfixe accepté).
_PRIORITY_DIRS = (
    "pictures", "images", "photos", "mes images", "camera", "desktop", "bureau",
    "documents", "downloads", "téléchargements", "telechargements", "onedrive",
    "creative cloud files", "videos", "vidéos",
)

# Dossiers ignorés : cachés (commencent par « . »), système, caches, logiciels,
# ressources d'applications (icônes Android, etc.).
_SKIP_DIR_NAMES = {
    "appdata", "application data", "local settings", "programdata", "$recycle.bin",
    "system volume information", "windows", "program files", "program files (x86)",
    "miniconda3", "anaconda3", "site-packages", "library", "cache", "caches",
    "temp", "tmp", "thumbnails", "node_modules", "__pycache__", "venv", "env",
    "dist", "build", "bin", "obj", "target", "go", "scikit_learn_data",
    "drawable", "mipmap", "res",
}
_SKIP_DIR_PREFIXES = ("drawable-", "mipmap-", "values-")

# ---------------------------------------------------------------------------
# État partagé
# ---------------------------------------------------------------------------

_index_progress: dict[str, Any] = {
    "status": "idle",
    "root": None,
    "current_file": None,
    "current_action": "En attente",
    "processed": 0,
    "total": 0,
    "percent": 0,
    "indexed": 0,
    "skipped": 0,
    "failed": 0,
    "error": None,
}
_index_lock = asyncio.Lock()
_index_task: asyncio.Task | None = None
_discovery_done: asyncio.Event | None = None
_last_scan_started = 0.0


def get_index_progress() -> dict[str, Any]:
    return dict(_index_progress)


def _set_index_progress(**values: Any) -> None:
    _index_progress.update(values)


def _report_path() -> Path:
    return settings.local_index_manifest_path.with_name("local_index_report.json")


def _read_report() -> dict[str, Any]:
    try:
        return json.loads(_report_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_report(data: dict[str, Any]) -> None:
    _report_path().parent.mkdir(parents=True, exist_ok=True)
    _report_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Chemins et extraction de texte
# ---------------------------------------------------------------------------


def _resolve_root(root_path: str) -> Path:
    requested_root = Path(root_path).expanduser()
    if not requested_root.is_absolute():
        requested_root = Path(settings.local_index_root) / requested_root
    return requested_root.resolve()


def _display_path(path: str) -> str:
    if path.startswith("/host-home/") and settings.local_host_root:
        return str(Path(settings.local_host_root) / Path(path.removeprefix("/host-home/")))
    return path


def extract_text_from_file(path: Path) -> str:
    suffix = path.suffix.lower()
    try:
        if suffix in _TEXT_EXTENSIONS:
            return path.read_text(encoding="utf-8", errors="replace")
        if suffix == ".pdf":
            pages = parse_pdf(str(path))
            return "\n\n".join(page.text for page in pages if page.text.strip())
        if suffix == ".docx":
            sections = parse_docx(str(path))
            return "\n\n".join(section.text for section in sections if section.text.strip())
    except Exception:
        return ""
    return ""


def _pdf_has_images(path: Path) -> bool:
    try:
        return any(page.images for page in parse_pdf(str(path)))
    except Exception:
        return False


def select_pdf_images(pages: list, limit: int) -> list[tuple[int, bytes]]:
    """Les images d'un PDF qui méritent une description : sans doublons (logos et captures
    répétés d'une page à l'autre), les plus lourdes d'abord, remises dans l'ordre des pages."""
    seen: set[bytes] = set()
    candidates: list[tuple[int, bytes]] = []
    for page in pages:
        for data in page.images:
            digest = hashlib.sha1(data).digest()
            if digest not in seen:
                seen.add(digest)
                candidates.append((page.page_number, data))
    best = sorted(candidates, key=lambda c: len(c[1]), reverse=True)[:max(limit, 0)]
    return sorted(best, key=lambda c: c[0])


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in _SUPPORTED_IMAGE_EXTENSIONS


# ---------------------------------------------------------------------------
# Découverte des fichiers
# ---------------------------------------------------------------------------


def _priority_key(name: str) -> int:
    lowered = name.lower()
    for rank, prefix in enumerate(_PRIORITY_DIRS):
        if lowered == prefix or lowered.startswith(prefix):
            return rank
    return len(_PRIORITY_DIRS)


def _skip_dir(name: str) -> bool:
    lowered = name.lower()
    if lowered.startswith("."):
        return True
    if lowered in _SKIP_DIR_NAMES or lowered.startswith(_SKIP_DIR_PREFIXES):
        return True
    return lowered in {d.lower() for d in settings.local_index_ignored_dirs}


def _image_is_meaningful(path: Path, size: int) -> bool:
    """Écarte icônes, pictogrammes et miniatures (peu de valeur, beaucoup de bruit)."""
    name = path.name.lower()
    if name.endswith(".9.png") or size < settings.local_min_image_bytes:
        return False
    try:
        from PIL import Image

        with Image.open(path) as image:
            width, height = image.size
    except Exception:
        return False
    return min(width, height) >= settings.local_min_image_side


def _discover(root: Path, max_files: int | None = None) -> tuple[list[Path], dict[str, Any]]:
    """Liste les fichiers à indexer, dossiers personnels d'abord.

    Le parcours est rapide (noms + tailles) ; la vérification des dimensions des images, plus lente
    sur un disque monté, se fait ensuite en parallèle."""
    from concurrent.futures import ThreadPoolExecutor

    limit = max(max_files or 0, settings.local_index_max_files)
    report: dict[str, Any] = {"skipped_small_images": 0, "truncated": False, "unreadable_dirs": 0}
    ordered: list[tuple[Path, bool]] = []  # (chemin, est_image)
    visited = {"dirs": 0}

    def walk(directory: str, top_level: bool) -> bool:
        try:
            entries = list(os.scandir(directory))
        except OSError:
            report["unreadable_dirs"] += 1
            return True
        visited["dirs"] += 1
        if visited["dirs"] % 25 == 0:
            _set_index_progress(current_action=f"Parcours : {visited['dirs']} dossiers, {len(ordered)} fichiers",
                                current_file=directory)
        if any(e.name == "pyvenv.cfg" for e in entries):
            return True  # environnement virtuel Python : aucun intérêt
        if top_level:
            entries.sort(key=lambda e: (_priority_key(e.name), e.name.lower()))
        else:
            entries.sort(key=lambda e: e.name.lower())
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    if _skip_dir(entry.name):
                        continue
                    if not walk(entry.path, False):
                        return False
                elif entry.is_file():
                    suffix = os.path.splitext(entry.name)[1].lower()
                    is_image = suffix in _SUPPORTED_IMAGE_EXTENSIONS
                    if not is_image and suffix not in _SUPPORTED_TEXT_EXTENSIONS:
                        continue
                    if is_image:
                        size = entry.stat().st_size
                        if entry.name.lower().endswith(".9.png") or size < settings.local_min_image_bytes:
                            report["skipped_small_images"] += 1
                            continue
                    if len(ordered) >= limit:
                        report["truncated"] = True
                        return False
                    ordered.append((Path(entry.path), is_image))
            except OSError:
                continue
        return True

    walk(str(root), True)

    _set_index_progress(current_action=f"Vérification de {sum(1 for _, i in ordered if i)} images")

    def keep(item: tuple[Path, bool]) -> bool:
        path, is_image = item
        if not is_image:
            return True
        try:
            from PIL import Image

            with Image.open(path) as image:
                return min(image.size) >= settings.local_min_image_side
        except Exception:
            return False

    with ThreadPoolExecutor(max_workers=16) as pool:
        flags = list(pool.map(keep, ordered))
    collected = [p for (p, is_image), ok in zip(ordered, flags) if ok]
    report["skipped_small_images"] += sum(1 for (_, is_image), ok in zip(ordered, flags) if is_image and not ok)
    report["discovered"] = len(collected)
    return collected, report


def _iter_files(root: Path, max_files: int) -> list[Path]:
    return _discover(root, max_files)[0]


def _stat_signature(path: Path) -> tuple[int, int, str]:
    stat = path.stat()
    return int(stat.st_mtime_ns), int(stat.st_size), datetime.fromtimestamp(stat.st_mtime).isoformat()


def _make_scan_item(file_path: Path) -> dict[str, Any] | None:
    text = extract_text_from_file(file_path)
    if not text.strip() and not is_image_file(file_path) and not (
        file_path.suffix.lower() == ".pdf" and _pdf_has_images(file_path)
    ):
        return None
    mtime_ns, size, modified_at = _stat_signature(file_path)
    return {
        "id": file_path.as_posix(),
        "path": file_path.as_posix(),
        "filename": file_path.name,
        "directory": str(file_path.parent),
        "extension": file_path.suffix.lower(),
        "content": text[:20000] if text.strip() else "Document visuel à décrire page par page.",
        "mtime_ns": mtime_ns,
        "size": size,
        "modified_at": modified_at,
    }


def scan_root(root: Path | str, max_files: int | None = None) -> list[dict[str, Any]]:
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists() or not root_path.is_dir():
        return []
    results: list[dict[str, Any]] = []
    for file_path in _discover(root_path, max_files)[0]:
        item = _make_scan_item(file_path)
        if item:
            results.append(item)
    return results


# ---------------------------------------------------------------------------
# Description des images
# ---------------------------------------------------------------------------


def _prepare_image(path: Path) -> tuple[bytes, str | None]:
    """Réduit l'image (plus rapide pour le modèle de vision) et lit la date de prise de vue."""
    from PIL import Image

    with Image.open(path) as image:
        taken = None
        try:
            exif = image.getexif()
            raw = exif.get_ifd(0x8769).get(36867) or exif.get(306)
            if raw:
                taken = datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S").isoformat()
        except Exception:
            taken = None
        image = image.convert("RGB")
        image.thumbnail((1024, 1024))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue(), taken


def _folder_hint(path: Path) -> str:
    parts = [p for p in path.parent.parts if p not in {"/", "\\"} and ":" not in p]
    return "/".join(parts[-2:])


def _image_document(item: dict[str, Any], description: str, taken_at: str | None) -> str:
    date = (taken_at or item["modified_at"])[:10]
    return (
        f"Photo « {item['filename']} » — dossier : {_folder_hint(Path(item['path']))} — date : {date}\n"
        f"{description}"
    )


# ---------------------------------------------------------------------------
# Indexation
# ---------------------------------------------------------------------------


def _collection_state() -> dict[str, dict[str, Any]]:
    """path -> métadonnées déjà indexées."""
    collection = local_collection()
    state: dict[str, dict[str, Any]] = {}
    offset = 0
    while True:
        batch = collection.get(include=["metadatas"], limit=2000, offset=offset)
        metas = batch.get("metadatas") or []
        if not metas:
            break
        for meta in metas:
            state[meta.get("path")] = meta
        offset += len(metas)
    return state


def _is_current(meta: dict[str, Any] | None, mtime_ns: int, size: int) -> bool:
    return bool(meta) and meta.get("mtime_ns") == mtime_ns and meta.get("size") == size


async def index_local_files(root_path: str, max_files: int | None = None) -> list[dict[str, Any]]:
    """Indexe le dossier et attend la fin (utilisé par l'API et la surveillance)."""
    async with _index_lock:
        return await _index_local_files(root_path, max_files)


async def _index_local_files(root_path: str, max_files: int | None = None) -> list[dict[str, Any]]:
    global _last_scan_started
    root = _resolve_root(root_path)
    if not root.is_dir():
        message = f"Dossier local introuvable : {root_path}"
        _set_index_progress(status="error", root=str(root), current_action="Dossier introuvable",
                            current_file=None, error=message)
        raise ValueError(message)

    _last_scan_started = time.time()
    _set_index_progress(status="scanning", root=str(root), current_file=None,
                        current_action="Parcours des dossiers", processed=0, total=0, percent=0,
                        indexed=0, skipped=0, failed=0, error=None)

    report = _read_report()
    if report.get("schema") != SCHEMA_VERSION:
        reset_local_collection()  # ancien format (icônes, descriptions génériques) : on repart propre
        report = {}
    collection = local_collection()

    files, discovery = await asyncio.to_thread(_discover, root, max_files)
    state = await asyncio.to_thread(_collection_state)
    current_paths = {p.as_posix() for p in files}

    for path in [p for p, meta in state.items() if meta.get("root_path") == root.as_posix() and p not in current_paths]:
        collection.delete(where={"path": path})
        state.pop(path, None)

    total = len(files)
    _set_index_progress(total=total, current_action="Comparaison avec l'index existant")
    failed: list[dict[str, str]] = []

    report_base = {
        "schema": SCHEMA_VERSION, "root": root.as_posix(), "started_at": datetime.now().isoformat(),
        "finished_at": None, "discovered": discovery["discovered"],
        "skipped_small_images": discovery["skipped_small_images"],
        "truncated": discovery["truncated"], "unreadable_dirs": discovery["unreadable_dirs"],
        "images_total": sum(1 for p in files if is_image_file(p)),
        "documents_total": sum(1 for p in files if not is_image_file(p)),
        "failed": [],
    }
    _write_report(report_base)
    if _discovery_done is not None:
        _discovery_done.set()

    # Ordre de traitement : documents texte (rapides) puis PDF puis images, chaque
    # groupe dans l'ordre de priorité des dossiers.
    def order(path: Path) -> int:
        if is_image_file(path):
            return 2
        return 1 if path.suffix.lower() == ".pdf" else 0

    ordered = sorted(files, key=order)  # tri stable : l'ordre de priorité est conservé
    items: list[dict[str, Any]] = []

    for processed, file_path in enumerate(ordered, start=1):
        path = file_path.as_posix()
        try:
            mtime_ns, size, modified_at = _stat_signature(file_path)
        except OSError:
            continue
        _set_index_progress(processed=processed, percent=round(processed / total * 100) if total else 100,
                            current_file=path)
        if _is_current(state.get(path), mtime_ns, size):
            _set_index_progress(skipped=_index_progress["skipped"] + 1)
            items.append({"id": path, "path": path})
            continue

        try:
            item = await _build_item(file_path)
        except Exception as exc:  # une erreur sur un fichier ne doit pas arrêter le scan
            item = None
            failed.append({"path": path, "reason": str(exc)[:200]})
            _set_index_progress(failed=len(failed))
        if not item:
            continue
        collection.delete(where={"path": path}) if path in state else None
        embeddings = await ollama_client.embed([item["content"]])
        collection.add(
            ids=[path],
            documents=[item["content"]],
            embeddings=embeddings,
            metadatas=[{
                "path": path, "filename": file_path.name, "directory": str(file_path.parent),
                "extension": file_path.suffix.lower(), "root_path": root.as_posix(),
                "modified_at": item.get("taken_at") or modified_at, "mtime_ns": mtime_ns, "size": size,
                "description": item.get("description", ""), "kind": item.get("kind", "document"),
            }],
        )
        items.append(item)
        _set_index_progress(indexed=_index_progress["indexed"] + 1)
        if _index_progress["indexed"] % 20 == 0:
            _write_report({**report_base, "failed": failed[-50:]})

    finished = {**report_base, "finished_at": datetime.now().isoformat(), "failed": failed[-50:],
                "failed_count": len(failed)}
    _write_report(finished)
    _set_index_progress(status="completed", current_file=None, current_action="Indexation terminée",
                        processed=total, total=total, percent=100)
    return items


async def _build_item(file_path: Path) -> dict[str, Any] | None:
    """Prépare le texte à indexer pour un fichier. Lève une exception si la description échoue :
    un fichier mal décrit ne doit jamais entrer dans l'index (il serait alors retrouvé pour de
    mauvaises raisons et jamais ré-essayé)."""
    if is_image_file(file_path):
        mtime_ns, size, modified_at = _stat_signature(file_path)
        item = {"id": file_path.as_posix(), "path": file_path.as_posix(), "filename": file_path.name,
                "modified_at": modified_at}
        _set_index_progress(current_action="Description de la photo")
        image_bytes, taken = await asyncio.to_thread(_prepare_image, file_path)
        description = await ollama_client.describe_image(image_bytes, PHOTO_DESCRIPTION_PROMPT)
        if len(description.strip()) < 20:
            raise RuntimeError("description vide")
        kind = "capture" if re.search(r"^type\s*:\s*capture", description, re.I | re.M) else (
            "photo" if re.search(r"^type\s*:\s*photo", description, re.I | re.M) else "image")
        return {**item, "description": description, "kind": kind, "taken_at": taken,
                "content": _image_document(item, description, taken)}

    item = await asyncio.to_thread(_make_scan_item, file_path)
    if not item:
        return None
    if item["extension"] == ".pdf":
        _set_index_progress(current_action="Analyse et description du PDF")
        pdf_pages = await asyncio.to_thread(parse_pdf, item["path"])
        images = select_pdf_images(pdf_pages, settings.local_pdf_max_images)
        page_descriptions: list[str] = []
        for k, (page_number, image) in enumerate(images, start=1):
            _set_index_progress(current_action=f"Description des images du PDF ({k}/{len(images)})")
            description = await ollama_client.describe_image(image)
            page_descriptions.append(f"Page {page_number} : {description}")
        text_description = ""
        if item["content"].strip() and not item["content"].startswith("Document visuel"):
            text_description = await ollama_client.describe_text(item["content"], item["filename"])
        description = "\n".join(part for part in [text_description, *page_descriptions] if part)
        item["description"] = description
        item["content"] = (
            f"Description du PDF {item['filename']} :\n{description}\n\nContenu extrait :\n{item['content']}"
        )
    item["kind"] = "document"
    return item


# ---------------------------------------------------------------------------
# Démarrage en arrière-plan et couverture
# ---------------------------------------------------------------------------


async def ensure_index(root_path: str | None = None, wait: bool = True) -> dict[str, Any]:
    """Lance (si besoin) l'indexation en arrière-plan et attend la fin de la découverte.

    Une question ne doit pas attendre que des milliers de photos soient décrites : elle attend
    seulement d'avoir la liste des fichiers, puis répond avec l'état de couverture réel."""
    global _index_task, _discovery_done
    root = str(_resolve_root(root_path or settings.local_index_root))
    running = _index_task is not None and not _index_task.done()
    stale = time.time() - _last_scan_started > settings.local_rescan_seconds
    if not running and stale:
        _discovery_done = asyncio.Event()

        async def run() -> None:
            try:
                await index_local_files(root)
            except Exception as exc:
                _set_index_progress(status="error", error=str(exc))
                if _discovery_done is not None:
                    _discovery_done.set()

        _index_task = asyncio.create_task(run())
        running = True
    if wait and running and _discovery_done is not None:
        try:
            await asyncio.wait_for(_discovery_done.wait(), settings.local_discovery_wait_seconds)
        except asyncio.TimeoutError:
            pass
    return await get_index_stats()


async def get_index_stats() -> dict[str, Any]:
    report = _read_report()
    state = await asyncio.to_thread(_collection_state)
    photos = sum(1 for m in state.values() if m.get("extension", "").lstrip(".") in _IMAGE_EXT_LIST)
    documents = len(state) - photos
    running = _index_task is not None and not _index_task.done()
    images_total = report.get("images_total", 0)
    documents_total = report.get("documents_total", 0)
    finished = bool(report.get("finished_at")) and not running
    failed = report.get("failed_count", len(report.get("failed", [])))
    complete = finished and not report.get("truncated") and failed == 0 and \
        photos >= images_total - failed and documents >= documents_total - failed
    top_folders: dict[str, int] = {}
    root = report.get("root", "")
    for path in state:
        rel = path[len(root):].lstrip("/") if root and path.startswith(root) else path
        top = rel.split("/")[0] if "/" in rel else "(racine)"
        top_folders[top] = top_folders.get(top, 0) + 1
    return {
        "root": root, "running": running, "complete": complete, "truncated": bool(report.get("truncated")),
        "images_indexed": photos, "images_total": images_total,
        "documents_indexed": documents, "documents_total": documents_total,
        "images_pending": max(0, images_total - photos - failed),
        "documents_pending": max(0, documents_total - documents - failed),
        "skipped_small_images": report.get("skipped_small_images", 0), "failed": failed,
        "finished_at": report.get("finished_at"), "top_folders": dict(sorted(top_folders.items(), key=lambda x: -x[1])[:12]),
    }


# ---------------------------------------------------------------------------
# Recherche
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "l", "et", "ou", "a", "au", "aux", "en",
    "dans", "sur", "sous", "que", "qui", "quoi", "ai", "as", "avons", "ont", "est", "sont", "je", "j",
    "tu", "il", "elle", "on", "nous", "vous", "me", "moi", "mes", "mon", "ma", "ton", "ta", "tes", "se",
    "ce", "cet", "cette", "ces", "pour", "par", "avec", "sans", "qu", "il", "y", "ya", "pris", "prise",
    "prises", "prendre", "fait", "faites", "ete", "etais", "tous", "toutes", "tout", "plus", "moins",
    "trouve", "trouver", "retrouve", "retrouver", "cherche", "chercher", "montre", "montrer", "donne",
    "photo", "photos", "image", "images", "fichier", "fichiers", "ordinateur", "pc", "dossier", "dossiers",
    "existe", "existent", "quelles", "quels", "quel", "quelle", "liste", "affiche",
}
_SYNONYMS = {
    "plage": ["plage", "mer", "sable", "ocean", "littoral", "vagues", "bord de mer", "cote"],
    "mer": ["mer", "plage", "ocean", "vagues", "eau", "bateau"],
    "montagne": ["montagne", "sommet", "alpes", "rocher", "randonnee", "col"],
    "neige": ["neige", "ski", "hiver", "glace", "enneige"],
    "foret": ["foret", "arbres", "bois", "sentier", "nature"],
    "ville": ["ville", "rue", "immeuble", "urbain", "batiment"],
    "voiture": ["voiture", "auto", "vehicule", "route"],
    "chat": ["chat", "chaton", "felin"],
    "chien": ["chien", "chiot", "canin"],
    "mariage": ["mariage", "noces", "marie", "mariee"],
    "anniversaire": ["anniversaire", "gateau", "bougies", "fete"],
    "coucher": ["coucher de soleil", "soleil couchant", "crepuscule"],
}
_PHOTO_RE = re.compile(r"\b(photos?|images?|selfies?|clich[ée]s?|captures? d.[ée]cran|screenshots?)\b", re.I)
_LOCATE_RE = re.compile(
    r"\b(trouv\w*|retrouv\w*|cherch\w*|montre\w*|liste\w*|affich\w*|o[uù]\s+(?:est|sont|se trouve\w*)|"
    r"y a[- ]t[- ]il|est[- ]ce que j.ai|ai[- ]je|est[- ]ce qu.il y a)\b|\bfichiers?\b|\bphotos?\b|\bimages?\b",
    re.I,
)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def query_keywords(query: str) -> list[str]:
    words = [w for w in re.split(r"[^a-z0-9]+", _fold(query)) if len(w) >= 3 and w not in _STOPWORDS]
    expanded: list[str] = []
    for word in words:
        expanded.append(word)
        for key, synonyms in _SYNONYMS.items():
            if word.startswith(key[:5]):
                expanded.extend(synonyms)
    return list(dict.fromkeys(expanded))


def is_photo_query(query: str) -> bool:
    return bool(_PHOTO_RE.search(query))


def is_locate_query(query: str) -> bool:
    return bool(_LOCATE_RE.search(query))


def _lexical_score(document: str, keywords: list[str]) -> int:
    folded = _fold(document)
    return sum(1 for kw in keywords if kw in folded)


def _hit(meta: dict[str, Any], text: str, distance: float | None, lexical: int) -> dict[str, Any]:
    path = meta.get("path", "")
    cosine = None if distance is None else round(max(0.0, 1.0 - float(distance) / 2.0), 3)
    return {
        "path": _display_path(path), "raw_path": path, "filename": meta.get("filename", Path(path).name),
        "directory": _display_path(meta.get("directory", str(Path(path).parent))),
        "extension": meta.get("extension", Path(path).suffix.lower()), "snippet": text[:400],
        "description": meta.get("description", ""), "kind": meta.get("kind", ""),
        "score": cosine if cosine is not None else 0.0, "cosine": cosine, "lexical": lexical,
        "modified_at": meta.get("modified_at"),
    }


def _passes_filters(meta: dict[str, Any], directory, extensions, after, before) -> bool:
    ext = meta.get("extension", "").lower().lstrip(".")
    modified_at = meta.get("modified_at")
    if directory and directory.lower() not in meta.get("directory", "").lower():
        return False
    if extensions and ext not in {e.lower().lstrip(".") for e in extensions}:
        return False
    if after and modified_at and modified_at < after:
        return False
    if before and modified_at and modified_at > before:
        return False
    return True


async def gather_candidates(
    query: str,
    root_path: str | None = None,
    directory: str | None = None,
    extensions: list[str] | None = None,
    modified_after: str | None = None,
    modified_before: str | None = None,
    photos_only: bool = False,
) -> list[dict[str, Any]]:
    """Candidats = recherche vectorielle ∪ recherche par mots-clés (les deux se complètent)."""
    collection = local_collection()
    resolved_root = _resolve_root(root_path).as_posix() if root_path else None
    clauses: list[dict[str, Any]] = []
    if resolved_root:
        clauses.append({"root_path": resolved_root})
    if photos_only:
        clauses.append({"extension": {"$in": [f".{e}" for e in _IMAGE_EXT_LIST]}})
    where = None if not clauses else (clauses[0] if len(clauses) == 1 else {"$and": clauses})

    candidates: dict[str, dict[str, Any]] = {}
    keywords = query_keywords(query)

    if collection.count():
        embedding = (await ollama_client.embed([query]))[0]
        n = min(settings.local_candidates * 2, collection.count())
        res = collection.query(query_embeddings=[embedding], n_results=max(n, 1), where=where,
                               include=["documents", "metadatas", "distances"])
        for text, meta, dist in zip((res.get("documents") or [[]])[0], (res.get("metadatas") or [[]])[0],
                                    (res.get("distances") or [[]])[0]):
            if _passes_filters(meta, directory, extensions, modified_after, modified_before):
                candidates[meta["path"]] = _hit(meta, text, dist, _lexical_score(text, keywords))

        if keywords:
            offset = 0
            while True:
                batch = collection.get(where=where, include=["documents", "metadatas"], limit=2000, offset=offset)
                metas = batch.get("metadatas") or []
                if not metas:
                    break
                for text, meta in zip(batch["documents"], metas):
                    if meta["path"] in candidates or not _passes_filters(
                            meta, directory, extensions, modified_after, modified_before):
                        continue
                    lex = _lexical_score(text, keywords)
                    if lex:
                        candidates[meta["path"]] = _hit(meta, text, None, lex)
                offset += len(metas)

    ranked = sorted(candidates.values(), key=lambda h: (h["lexical"] > 0, h["lexical"], h["cosine"] or 0), reverse=True)
    return ranked[: settings.local_candidates]


_JUDGE_SYSTEM = (
    "Tu vérifies si des fichiers de l'ordinateur répondent à la demande d'un utilisateur, "
    "à partir de leur description. Réponds en JSON strict : {\"correspond\": [numéros]}.\n"
    "Règles : ne retiens un fichier que si sa description montre CLAIREMENT ce qui est demandé "
    "(le lieu, la scène, l'objet ou le sujet précis). Une simple ressemblance de couleur ou de forme "
    "ne suffit pas. Une icône, un logo ou une capture d'écran n'est pas une photo de lieu. "
    "En cas de doute, ne retiens pas le fichier. S'il n'y en a aucun, réponds {\"correspond\": []}."
)


def _parse_judge(raw: str, valid: int) -> list[int]:
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        raise ValueError("réponse non JSON")
    numbers = json.loads(match.group(0)).get("correspond", [])
    return [int(n) for n in numbers if isinstance(n, (int, float, str)) and str(n).lstrip("-").isdigit()
            and 1 <= int(n) <= valid]


async def judge_candidates(query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Garde les candidats qui répondent vraiment. None si le jugement est impossible."""
    kept: list[dict[str, Any]] = []
    pool = candidates[: settings.local_judge_max]
    for start in range(0, len(pool), settings.local_judge_batch):
        batch = pool[start:start + settings.local_judge_batch]
        listing = "\n\n".join(
            f"[{i}] {c['filename']} ({c['extension']})\n{(c['description'] or c['snippet'])[:700]}"
            for i, c in enumerate(batch, start=1)
        )
        try:
            raw = await ollama_client.chat_once(
                [{"role": "system", "content": _JUDGE_SYSTEM},
                 {"role": "user", "content": f"Demande : {query}\n\nFichiers :\n{listing}"}],
                json_format=True,
            )
            picked = _parse_judge(raw, len(batch))
        except Exception:
            return None
        kept.extend(batch[i - 1] for i in picked)
    return kept


async def find_matches(
    query: str,
    root_path: str | None = None,
    directory: str | None = None,
    extensions: list[str] | None = None,
    modified_after: str | None = None,
    modified_before: str | None = None,
) -> dict[str, Any]:
    photos_only = is_photo_query(query) and not extensions
    candidates = await gather_candidates(query, root_path, directory, extensions, modified_after,
                                         modified_before, photos_only=photos_only)
    judged = await judge_candidates(query, candidates) if candidates else []
    if judged is None:  # modèle indisponible : seuil de similarité + mot-clé (photos)
        keywords = query_keywords(query)
        judged = [c for c in candidates
                  if (c["cosine"] or 0) >= settings.local_min_cosine and (c["lexical"] > 0 or not keywords)]
        method = "seuil"
    else:
        method = "jugement"
    return {"matches": judged, "examined": len(candidates), "method": method, "photos_only": photos_only}


async def search_local_files(
    query: str,
    limit: int = 5,
    root_path: str | None = None,
    directory: str | None = None,
    extensions: list[str] | None = None,
    modified_after: str | None = None,
    modified_before: str | None = None,
) -> list[dict[str, Any]]:
    """Recherche « brute » (endpoint /search) : les candidats jugés pertinents, sans réponse rédigée."""
    if not query.strip():
        return []
    outcome = await find_matches(query, root_path, directory, extensions, modified_after, modified_before)
    return outcome["matches"][:limit]
