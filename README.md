# RAG Local — assistant documentaire 100% privé

Chat avec tes documents (PDF, Word, texte) **entièrement en local**. Aucune donnée —
ni le contenu des documents, ni les questions posées — ne quitte jamais la machine.
Pensé pour des usages sensibles à la confidentialité (juridique, conseil, santé) où
envoyer des documents à une API cloud (OpenAI, etc.) n'est pas une option.

## Pourquoi ce projet

Assemblé à partir de projets open-source éprouvés plutôt que réécrit from scratch :
[Ollama](https://github.com/ollama/ollama) (inférence LLM locale), [Chroma](https://github.com/chroma-core/chroma)
(base vectorielle embarquée), `pypdf` / `python-docx` (parsing de documents),
`langchain-text-splitters` (découpage), FastAPI et Next.js/shadcn pour l'assemblage
et l'interface. La partie écrite à la main — l'orchestration RAG, le système de
citations et le streaming — reste volontairement simple et lisible (~300 lignes) :
c'est la partie qui démontre la compréhension du pipeline, plutôt que de la cacher
derrière un framework RAG tout-en-un.

## Fonctionnalités

- Import de PDF / DOCX / TXT, découpage et indexation vectorielle locale
- Chat en streaming avec réponses **citées** (`[1]`, `[2]`...) renvoyant au document
  et à la page/section source exacte
- Le modèle refuse explicitement de répondre si l'information n'est pas dans les
  documents fournis, plutôt que d'halluciner
- **Images comprises** : toute image significative (>3 Ko — filtre les icônes
  décoratives) rencontrée dans un PDF ou un DOCX — page scannée, capture d'écran,
  graphique, tableau photographié — est décrite/transcrite automatiquement par un
  modèle de vision local (`qwen3-vl:4b`) et devient cherchable comme du texte normal
- Sélection des documents à interroger (un, plusieurs, ou toute la bibliothèque)
- Bannière d'état si Ollama est injoignable ou qu'un modèle requis est manquant

## Stack

| Couche | Choix |
|---|---|
| LLM local | [Ollama](https://ollama.com), natif sur l'hôte (pas conteneurisé, voir plus bas) |
| Modèle de chat | `qwen3:8b` (fallback documenté : `qwen2.5:7b-instruct-q4_K_M`) |
| Modèle de vision | `qwen3-vl:4b` via Ollama (OCR + description d'images, 3,3 Go) |
| Embeddings | `nomic-embed-text` via Ollama |
| Base vectorielle | Chroma (embarqué, `PersistentClient`) |
| Backend | FastAPI + Uvicorn, Python 3.12 |
| Frontend | Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui |
| Transport streaming | Server-Sent Events (SSE) |

## Démarrage rapide

```bash
# 1. Prérequis : Ollama installé (https://ollama.com) et lancé, Docker Desktop
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1

# 2. Lancer l'app
docker-compose up --build
```

Ouvre [http://localhost:3000](http://localhost:3000).

### Dev local (sans Docker)

```bash
# Backend
cd backend
py -3.13 -m venv .venv          # python 3.10-3.13 conviennent (pas de dépendance ML lourde)
./.venv/Scripts/pip install -r requirements.txt
./.venv/Scripts/python -m uvicorn app.main:app --reload

# Frontend (autre terminal)
cd frontend
npm install
npm run dev
```

> Sous Windows, `--reload` peut se bloquer sur un redémarrage si Chroma a un
> verrou actif sur son fichier SQLite interne : si un rechargement semble figé,
> relance simplement le process (Ctrl+C puis restart) plutôt que d'attendre.

## Pourquoi Ollama n'est pas dans Docker

Sous Windows, le passthrough GPU pour un conteneur Ollama est fragile (dépend de
l'alignement pilote NVIDIA / WSL2 / `nvidia-container-toolkit`). Ollama tourne déjà
nativement avec accès GPU sans configuration supplémentaire — le backend Docker
l'appelle via `host.docker.internal:11434`. Un bloc de service `ollama` (Linux +
GPU NVIDIA) est fourni en commentaire dans `docker-compose.yml`.

## Preuve du "100% local"

Coupe le réseau, puis importe un document et pose une question : tout continue de
fonctionner. C'est la démonstration la plus parlante de l'architecture.

## Limitations connues (choix de scope, pas des oublis)

- La transcription par IA vision (page scannée, image) peut être imprécise — un
  avertissement s'affiche systématiquement à l'import et invite à vérifier les
  passages importants ; ce n'est pas un OCR déterministe classique
- Les images de moins de 3 Ko (icônes, puces décoratives) sont ignorées d'office
  pour éviter de saturer le pipeline avec du bruit sans intérêt informationnel
- Les tableaux DOCX sont bien extraits (texte des cellules, `|`-séparé) ; pour les
  PDF, `pypdf` extrait le texte des tableaux mais sans garantie de préserver
  l'ordre exact des colonnes sur des mises en page complexes
- Mono-utilisateur, pas d'authentification — pensé pour un usage local individuel
- Pas de reranking ni de réécriture de requête multi-tour (voir pistes ci-dessous)

## Pistes d'amélioration

Reranking cross-encoder, recherche hybride BM25 + vectorielle, réécriture de
requête multi-tour, jeu d'évaluation type RAGAS, CI GitHub Actions.
