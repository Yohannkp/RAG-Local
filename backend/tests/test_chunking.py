from app.services.chunking import chunk_units


def test_chunk_respects_size_and_overlap():
    long_text = "Phrase numero un. " * 300  # bien plus grand qu'un chunk
    chunks = chunk_units([(long_text, {"page_number": 1})])

    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text) <= 2400 + 50  # petite marge pour ne pas couper un mot


def test_chunks_never_cross_unit_boundary():
    units = [
        ("Contenu de la page un.", {"page_number": 1}),
        ("Contenu de la page deux.", {"page_number": 2}),
    ]
    chunks = chunk_units(units)

    assert len(chunks) == 2
    assert chunks[0].metadata["page_number"] == 1
    assert chunks[1].metadata["page_number"] == 2
    assert "page un" in chunks[0].text
    assert "page deux" in chunks[1].text


def test_empty_units_are_skipped():
    units = [("", {"page_number": 1}), ("   ", {"page_number": 2})]
    assert chunk_units(units) == []


def test_chunk_index_and_char_offsets_are_set():
    chunks = chunk_units([("Un texte court.", {"section_title": "Intro"})])
    assert chunks[0].metadata["chunk_index"] == 0
    assert chunks[0].metadata["char_start"] == 0
    assert chunks[0].metadata["char_end"] == len("Un texte court.")
