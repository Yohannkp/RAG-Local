FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Precharge le modele de reranking (cross-encoder, ~470 Mo) pendant le build :
# sans ca, la toute premiere requete apres un demarrage de conteneur devrait
# le telecharger a la volee, la rendant tres lente (~30-60s) sans raison
# apparente pour l'utilisateur.
RUN python -c "from app.core.reranker import _get_model; _get_model()"

ENV RAG_OLLAMA_BASE_URL=http://host.docker.internal:11434

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
