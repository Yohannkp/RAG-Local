import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="rag-tests-")
os.environ["RAG_DATA_DIR"] = _tmp
os.environ["RAG_CHROMA_DIR"] = os.path.join(_tmp, "chroma")
os.environ["RAG_UPLOADS_DIR"] = os.path.join(_tmp, "uploads")
os.environ["RAG_LOCAL_INDEX_MANIFEST_PATH"] = os.path.join(_tmp, "manifest.json")
