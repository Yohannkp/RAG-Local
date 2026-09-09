# RAG Local — assistant documentaire 100% privé

Chat avec tes documents (PDF, Word, texte) **entièrement en local**. Aucune donnée —
ni le contenu des documents, ni les questions posées — ne quitte jamais la machine.
Pensé pour des usages sensibles à la confidentialité (juridique, conseil, santé) où
envoyer des documents à une API cloud (OpenAI, etc.) n'est pas une option.

## Pourquoi ce projet

Assemblé à partir de projets open-source éprouvés plutôt que réécrit from scratch :
[Ollama](https://github.com/ollama/ollama) (inférence LLM locale), [Chroma](https://github.com/chroma-core/chroma)
(base vectorielle embarquée), `pypdf` / `python-docx` (parsing de documents),
`langchain-text-splitters` (découpage), `rank-bm25` (recherche lexicale),
`sentence-transformers` (reranking cross-encoder), [RAGAS](https://github.com/explodinggradients/ragas)
(évaluation), `react-pdf` (visionneuse), FastAPI et Next.js/shadcn pour
l'assemblage et l'interface. La partie écrite à la main — l'orchestration RAG, le
système de citations, le streaming, la fusion hybride — reste volontairement simple
et lisible : c'est la partie qui démontre la compréhension du pipeline, plutôt que
de la cacher derrière un framework RAG tout-en-un.

## Fonctionnalités

- Import de PDF / DOCX / TXT, découpage et indexation vectorielle locale
- **Recherche hybride** : fusion (Reciprocal Rank Fusion) d'une recherche
  vectorielle sémantique et d'une recherche lexicale BM25, puis **reranking**
  par cross-encoder local (`mmarco-mMiniLMv2-L12-H384-v1`, CPU) — le pipeline
  standard "retrieve top-N hybride → rerank top-k" pour une meilleure précision
  qu'un simple `top_k` vectoriel, y compris sur les noms propres/références exactes
- **Réécriture de requête multi-tour** : une question de suivi ambiguë ("et pour
  les mineurs ?") est reformulée en question autonome à partir de l'historique
  avant la recherche, sinon elle ne retrouverait quasiment rien de pertinent
- Chat en streaming avec réponses **citées** (`[1]`, `[2]`...) renvoyant au document
  et à la page/section source exacte
- **Visionneuse de source intégrée** : cliquer sur une citation PDF ouvre la page
  exacte du document original (`react-pdf`) ; pour DOCX/TXT, affiche le passage
  complet non tronqué — vérifier une réponse ne demande jamais de quitter l'app
- **Dictée vocale** (Web Speech API du navigateur) pour poser une question à l'oral
- Le modèle refuse explicitement de répondre si l'information n'est pas dans les
  documents fournis, plutôt que d'halluciner
- **Images comprises** : toute image significative (>3 Ko — filtre les icônes
  décoratives) rencontrée dans un PDF ou un DOCX — page scannée, capture d'écran,
  graphique, tableau photographié — est décrite/transcrite automatiquement par un
  modèle de vision local (`qwen3-vl:4b`) et devient cherchable comme du texte normal
- **Recherche automatique sur toute la bibliothèque par défaut** — pas besoin de
  sélectionner un document à chaque question, même avec beaucoup de fichiers
  importés ; la sélection manuelle reste possible pour restreindre la recherche
  à un ou plusieurs documents précis
- Bannière d'état si Ollama est injoignable ou qu'un modèle requis est manquant
- **Suite d'évaluation RAGAS locale** (voir [Évaluation](#évaluation)) : mesure
  faithfulness / context precision / context recall / answer relevancy sur le
  pipeline réel, avec le modèle de chat local comme juge — aucun appel externe

## Stack

| Couche | Choix |
|---|---|
| LLM local | [Ollama](https://ollama.com), natif sur l'hôte (pas conteneurisé, voir plus bas) |
| Modèle de chat | `qwen3:8b` (fallback documenté : `qwen2.5:7b-instruct-q4_K_M`) |
| Modèle de vision | `qwen3-vl:4b` via Ollama (OCR + description d'images, 3,3 Go) |
| Embeddings | `nomic-embed-text` via Ollama |
| Recherche lexicale | `rank-bm25` (Okapi BM25), fusionnée au vectoriel via RRF |
| Reranking | `sentence-transformers` `CrossEncoder`, CPU (le GPU reste dédié à Ollama) |
| Base vectorielle | Chroma (embarqué, `PersistentClient`) |
| Backend | FastAPI + Uvicorn, Python 3.12 |
| Frontend | Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui |
| Visionneuse PDF | `react-pdf` (pdf.js), worker servi localement (pas de CDN) |
| Transport streaming | Server-Sent Events (SSE) |
| Évaluation | RAGAS, juge = `qwen3:8b` via `langchain-ollama` |

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
fonctionner. C'est la démonstration la plus parlante de l'architecture. Le
téléchargement ponctuel des modèles Ollama/HuggingFace (une fois, à l'installation)
est la seule étape qui nécessite Internet — rien à l'usage.

## Évaluation

```bash
cd backend
./.venv/Scripts/python eval/run_eval.py
```

Ingère un document fixture (`eval/fixture_document.txt`, 5 sujets distincts +
1 question hors-sujet pour vérifier l'absence d'hallucination), exécute le jeu de
questions de référence (`eval/dataset.py`) à travers le **pipeline réel**
(recherche hybride + reranking + génération), puis calcule les métriques RAGAS
avec `qwen3:8b` comme juge local. Résultats détaillés sauvegardés dans
`eval/last_run_results.json` ; le document fixture est supprimé automatiquement
en fin d'exécution (n'affecte pas ta bibliothèque de documents réels).

## Limitations connues (choix de scope, pas des oublis)

- La transcription par IA vision (page scannée, image) peut être imprécise — un
  avertissement s'affiche systématiquement à l'import et invite à vérifier les
  passages importants ; ce n'est pas un OCR déterministe classique
- Les images de moins de 3 Ko (icônes, puces décoratives) sont ignorées d'office
  pour éviter de saturer le pipeline avec du bruit sans intérêt informationnel
- Les tableaux DOCX sont bien extraits (texte des cellules, `|`-séparé) ; pour les
  PDF, `pypdf` extrait le texte des tableaux mais sans garantie de préserver
  l'ordre exact des colonnes sur des mises en page complexes
- La dictée vocale utilise l'API de reconnaissance vocale du navigateur : selon le
  navigateur (Chrome notamment), elle peut passer par un service en ligne — seule
  fonctionnalité de l'app qui n'est pas garantie 100% locale
- `sentence-transformers`/`torch` (reranking) alourdissent significativement
  l'image Docker du backend (~1-2 Go) ; le reranker tourne en CPU pur, le GPU
  restant entièrement dédié à Ollama
- Mono-utilisateur, pas d'authentification — pensé pour un usage local individuel
- La recherche par défaut porte sur toute la bibliothèque : le corpus BM25 est
  reconstruit à chaque question à partir de tous les chunks des documents
  ciblés. Très bien à l'échelle d'un usage personnel (dizaines à quelques
  centaines de documents) ; à plusieurs milliers de documents, ça deviendrait
  le goulot d'étranglement (voir pistes ci-dessous)

## Pistes d'amélioration

Index BM25 persistant (au lieu d'être reconstruit à chaque question) pour tenir
à l'échelle de milliers de documents, GraphRAG pour le raisonnement
inter-documents, boucle agentique (le modèle décide de re-chercher s'il manque
d'information), OCR dédié (`pytesseract`) en complément de l'analyse par vision
pour les cas ambigus, CI GitHub Actions exécutant `eval/` comme gate de
qualité, gestion de l'historique de conversation persistant
(actuellement en mémoire côté client uniquement).
