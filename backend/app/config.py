from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    chat_model: str = "qwen3:8b"
    embed_model: str = "nomic-embed-text"
    vision_model: str = "qwen3-vl:4b"
    num_ctx: int = 8192

    # Combien de temps Ollama garde chaque modèle chargé en VRAM après le
    # dernier appel (au-delà, il faut recharger à froid, ~20-30s). Chat et
    # vision ne tiennent pas en même temps sur un GPU 8 Go : le modèle de
    # vision reste chargé le moins longtemps possible pour rendre la VRAM au
    # modèle de chat aussitôt un import terminé, plutôt que de la monopoliser
    # inutilement pendant 5 minutes (défaut Ollama) après une simple analyse
    # d'image ponctuelle.
    chat_keep_alive: str = "30m"
    embed_keep_alive: str = "30m"
    vision_keep_alive: str = "1m"

    # Chunks plus petits = moins de risque qu'un chunk mélange plusieurs
    # sous-sections différentes d'une même page dense (ça dilue la pertinence
    # sémantique du chunk pour n'importe laquelle des sous-sections qu'il
    # contient). Affecte seulement les nouveaux imports — les documents déjà
    # indexés gardent leur découpage existant sauf réimport.
    chunk_size_chars: int = 1200
    chunk_overlap_chars: int = 150
    # 6 plutôt que 5 : rattrape les cas où un passage pertinent finit juste
    # hors du top-5 après reranking (observé en pratique, voir README).
    top_k: int = 6

    # Recherche hybride : nombre de candidats remontés par chaque méthode
    # (BM25 + vectoriel) avant fusion RRF et reranking.
    hybrid_candidates: int = 20
    reranker_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    # Recherche locale sur le disque : indexe un dossier racine local pour des
    # interrogations rapides du type "ou est ce fichier ?".
    local_index_root: str = str(Path.home())
    local_host_root: str = ""
    # Plafond de sécurité seulement : le scan doit couvrir tout le disque pour
    # pouvoir affirmer qu'un fichier n'existe pas. S'il est atteint, l'analyse
    # est marquée « tronquée » et l'assistant ne prétend plus avoir tout vu.
    local_index_max_files: int = 200000
    # Images plus petites que ça = icônes, pictogrammes, miniatures : ignorées.
    local_min_image_bytes: int = 30_000
    local_min_image_side: int = 200
    # Images décrites par PDF (les plus lourdes, sans doublons). Un guide logiciel peut en
    # contenir des centaines : 713 pour un PDF de 23 pages, soit deux heures de modèle de vision.
    local_pdf_max_images: int = 6
    # Nouveau scan automatique avant une question si le dernier date de plus de…
    local_rescan_seconds: int = 300
    # Combien de temps une question attend la fin de la phase de découverte.
    local_discovery_wait_seconds: float = 20.0
    # Repli si le modèle de chat ne peut pas juger les candidats : cosinus minimal.
    # Surveillance temps réel : inutile (et coûteuse) sur un montage Docker ; un re-scan
    # incrémental est lancé à chaque question.
    local_watch_enabled: bool = False
    local_min_cosine: float = 0.62
    # Nombre de candidats examinés (recherche vectorielle + mots-clés) puis jugés.
    local_candidates: int = 40
    local_judge_batch: int = 10
    local_judge_max: int = 30
    local_index_manifest_path: Path = DATA_DIR / "local_index_manifest.json"
    local_index_ignored_dirs: list[str] = [
        ".git",
        ".idea",
        ".vscode",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".next",
        "dist",
        "build",
        "bin",
        "obj",
        "target",
    ]
    data_dir: Path = DATA_DIR
    uploads_dir: Path = DATA_DIR / "uploads"
    chroma_dir: Path = DATA_DIR / "chroma"
    sqlite_path: Path = DATA_DIR / "registry.db"

    model_config = SettingsConfigDict(env_prefix="RAG_")


settings = Settings()
settings.uploads_dir.mkdir(parents=True, exist_ok=True)
settings.chroma_dir.mkdir(parents=True, exist_ok=True)
