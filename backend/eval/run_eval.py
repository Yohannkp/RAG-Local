"""Evalue le pipeline RAG (recherche hybride + reranking + generation) avec
RAGAS, en utilisant le modele de chat local (Ollama) comme juge — aucun appel
a une API externe. Ingere un document fixture connu, pose un jeu de questions
de reference, mesure faithfulness / context precision / context recall /
answer relevancy, puis nettoie le document fixture.

Usage (depuis backend/, avec le venv active et Ollama qui tourne) :
    python eval/run_eval.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_ollama import ChatOllama, OllamaEmbeddings  # noqa: E402
from ragas import EvaluationDataset, SingleTurnSample, evaluate  # noqa: E402
from ragas.embeddings import LangchainEmbeddingsWrapper  # noqa: E402
from ragas.llms import LangchainLLMWrapper  # noqa: E402
from ragas.metrics import (  # noqa: E402
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
)
from ragas.run_config import RunConfig  # noqa: E402

# Un seul juge Ollama local (un seul GPU, un seul modele charge) : le
# parallelisme par defaut de RAGAS (16 workers) sature la file d'attente
# d'Ollama et fait timeout en cascade sur les metriques multi-appels
# (faithfulness). On serialise fortement et on augmente la marge de timeout.
EVAL_RUN_CONFIG = RunConfig(timeout=300, max_workers=2)

from app.config import settings  # noqa: E402
from app.core.db import init_db  # noqa: E402
from app.services import ingestion_service, retrieval_service  # noqa: E402
from eval.dataset import GOLDEN_SET  # noqa: E402

FIXTURE_PATH = Path(__file__).parent / "fixture_document.txt"
METRICS = ["faithfulness", "context_precision", "context_recall", "answer_relevancy"]


async def _collect_samples(doc_id: str) -> list[SingleTurnSample]:
    samples = []
    for item in GOLDEN_SET:
        answer = ""
        contexts: list[str] = []
        async for kind, payload in retrieval_service.stream_answer(
            item["question"], [doc_id], []
        ):
            if kind == "sources":
                contexts = [s.snippet for s in payload]
            elif kind == "token":
                answer += payload
        samples.append(
            SingleTurnSample(
                user_input=item["question"],
                retrieved_contexts=contexts or ["(aucun extrait retrouvé)"],
                response=answer,
                reference=item["ground_truth"],
            )
        )
        print(f"  [ok] {item['question'][:65]}")
    return samples


async def main() -> None:
    init_db()
    print(f"Ingestion du document fixture ({FIXTURE_PATH.name})...")
    doc = await ingestion_service.ingest_file(FIXTURE_PATH, "eval_fixture.txt", "txt")

    try:
        print(f"Execution des {len(GOLDEN_SET)} questions du jeu de reference...")
        samples = await _collect_samples(doc.id)

        judge_llm = LangchainLLMWrapper(
            ChatOllama(model=settings.chat_model, base_url=settings.ollama_base_url)
        )
        judge_embeddings = LangchainEmbeddingsWrapper(
            OllamaEmbeddings(model=settings.embed_model, base_url=settings.ollama_base_url)
        )

        print("\nCalcul des métriques RAGAS (juge : modèle local via Ollama, "
              "peut prendre plusieurs minutes)...")
        result = evaluate(
            dataset=EvaluationDataset(samples=samples),
            metrics=[Faithfulness(), ContextPrecision(), ContextRecall(), AnswerRelevancy()],
            llm=judge_llm,
            embeddings=judge_embeddings,
            run_config=EVAL_RUN_CONFIG,
        )

        df = result.to_pandas()

        print("\n" + "=" * 72)
        print("RÉSULTATS PAR QUESTION")
        print("=" * 72)
        for i, row in df.iterrows():
            item = GOLDEN_SET[i]
            flag = "  [hors-sujet attendu]" if item["is_unanswerable"] else ""
            print(f"\n[{i + 1}] {item['question']}{flag}")
            print(
                "    "
                + "  ".join(f"{m}={row.get(m, float('nan')):.2f}" for m in METRICS)
            )

        print("\n" + "-" * 72)
        print("MOYENNES")
        for metric in METRICS:
            print(f"  {metric}: {df[metric].mean():.3f}")
        print("-" * 72)

        out_path = Path(__file__).parent / "last_run_results.json"
        df.to_json(out_path, orient="records", force_ascii=False, indent=2)
        print(f"\nRésultats détaillés sauvegardés dans {out_path}")

    finally:
        print(f"\nNettoyage : suppression du document fixture ({doc.id})...")
        ingestion_service.delete_document(doc.id)


if __name__ == "__main__":
    asyncio.run(main())
