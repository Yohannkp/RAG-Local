from app.services.ingestion_service import _build_docx_warning, _build_pdf_warning


def test_pdf_warning_none_when_all_pages_have_text_and_no_images():
    assert _build_pdf_warning(empty_pages=[], images_analyzed=0, total_pages=5) is None


def test_pdf_warning_none_when_empty_pages_but_images_covered_them():
    # une page detectee "vide" par extract_text() peut avoir ete recuperee
    # via l'analyse d'image (page scannee) : elle ne doit plus apparaitre
    # dans empty_pages a ce stade (c'est le rappelant qui gere ca), donc ici
    # empty_pages=[] + images_analyzed>0 = note informative, pas d'alerte.
    warning = _build_pdf_warning(empty_pages=[], images_analyzed=1, total_pages=2)
    assert warning is not None
    assert "analysée" in warning
    assert "vérifie les passages importants" in warning


def test_pdf_warning_partial_empty_names_the_pages():
    warning = _build_pdf_warning(empty_pages=[3, 7], images_analyzed=0, total_pages=10)
    assert warning is not None
    assert "3, 7" in warning
    assert "Les pages" in warning
    assert "reste du document est indexé" in warning


def test_pdf_warning_partial_empty_singular_page():
    warning = _build_pdf_warning(empty_pages=[2], images_analyzed=0, total_pages=2)
    assert warning is not None
    assert "La page 2 est vide" in warning
    assert "son contenu" in warning


def test_pdf_warning_fully_empty_document():
    warning = _build_pdf_warning(empty_pages=[1, 2], images_analyzed=0, total_pages=2)
    assert warning is not None
    assert "entièrement scanné" in warning


def test_docx_warning_none_without_images():
    assert _build_docx_warning(0) is None


def test_docx_warning_mentions_image_count():
    warning = _build_docx_warning(2)
    assert warning is not None
    assert "2 images analysées" in warning
