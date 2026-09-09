from docx import Document as DocxDocument

from app.core.parsing import docx_parser
from app.core.parsing.docx_parser import parse_docx
from app.core.parsing.pdf_parser import PageUnit, find_empty_pages
from app.core.parsing.txt_parser import parse_txt

# PNG 1x1 blanc minimal valide, utilisé pour tester l'extraction d'images
# sans dépendre de Pillow (non requis par le projet).
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01"
    b"\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_parse_docx_groups_paragraphs_under_headings(tmp_path):
    doc = DocxDocument()
    doc.add_heading("Introduction", level=1)
    doc.add_paragraph("Ceci est le texte d'introduction.")
    doc.add_heading("Conditions", level=1)
    doc.add_paragraph("Ceci decrit les conditions.")
    path = tmp_path / "test.docx"
    doc.save(str(path))

    sections = parse_docx(str(path))

    titles = [s.section_title for s in sections]
    assert "Introduction" in titles
    assert "Conditions" in titles
    intro = next(s for s in sections if s.section_title == "Introduction")
    assert "introduction" in intro.text


def test_parse_docx_without_headings_falls_back_to_single_section(tmp_path):
    doc = DocxDocument()
    doc.add_paragraph("Juste un paragraphe, sans titre.")
    path = tmp_path / "no_heading.docx"
    doc.save(str(path))

    sections = parse_docx(str(path))

    assert len(sections) == 1
    assert "paragraphe" in sections[0].text


def test_parse_docx_includes_table_content(tmp_path):
    doc = DocxDocument()
    doc.add_heading("Tarifs", level=1)
    doc.add_paragraph("Grille tarifaire ci-dessous.")
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Formule"
    table.rows[0].cells[1].text = "Prix"
    table.rows[1].cells[0].text = "Standard"
    table.rows[1].cells[1].text = "99 euros"
    path = tmp_path / "tarifs.docx"
    doc.save(str(path))

    sections = parse_docx(str(path))

    tarifs = next(s for s in sections if s.section_title == "Tarifs")
    assert "Formule" in tarifs.text
    assert "99 euros" in tarifs.text


def test_parse_docx_table_before_any_heading_is_captured(tmp_path):
    doc = DocxDocument()
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Cle"
    table.rows[0].cells[1].text = "Valeur"
    path = tmp_path / "table_first.docx"
    doc.save(str(path))

    sections = parse_docx(str(path))

    assert any("Cle" in s.text and "Valeur" in s.text for s in sections)


def test_parse_txt_reads_utf8(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("Texte avec des accents : éàç", encoding="utf-8")

    assert parse_txt(str(path)) == "Texte avec des accents : éàç"


def test_find_empty_pages_detects_fully_scanned_document():
    mostly_empty = [PageUnit(page_number=i, text="") for i in range(1, 5)]
    assert find_empty_pages(mostly_empty) == [1, 2, 3, 4]


def test_find_empty_pages_empty_for_real_text():
    normal = [
        PageUnit(page_number=i, text="Un paragraphe de contenu bien réel." * 3)
        for i in range(1, 5)
    ]
    assert find_empty_pages(normal) == []


def test_find_empty_pages_flags_a_single_image_page_in_otherwise_normal_doc():
    units = [
        PageUnit(page_number=1, text="Un paragraphe de contenu bien réel." * 3),
        PageUnit(page_number=2, text=""),  # page image, sans texte
    ]
    assert find_empty_pages(units) == [2]


def test_parse_docx_no_images_when_none_embedded(tmp_path):
    doc = DocxDocument()
    doc.add_paragraph("Aucune image ici.")
    path = tmp_path / "no_image.docx"
    doc.save(str(path))

    sections = parse_docx(str(path))

    assert all(s.images == [] for s in sections)


def test_parse_docx_extracts_embedded_image_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(docx_parser, "_MIN_MEANINGFUL_IMAGE_BYTES", 10)
    img_path = tmp_path / "pixel.png"
    img_path.write_bytes(_TINY_PNG)

    doc = DocxDocument()
    doc.add_heading("Photo", level=1)
    doc.add_picture(str(img_path))
    path = tmp_path / "with_image.docx"
    doc.save(str(path))

    sections = parse_docx(str(path))

    photo = next(s for s in sections if s.section_title == "Photo")
    assert len(photo.images) == 1
    assert photo.images[0] == _TINY_PNG


def test_parse_docx_ignores_tiny_decorative_images(tmp_path):
    img_path = tmp_path / "icon.png"
    img_path.write_bytes(_TINY_PNG)

    doc = DocxDocument()
    doc.add_paragraph("Texte avec une petite icone.")
    doc.add_picture(str(img_path))
    path = tmp_path / "with_icon.docx"
    doc.save(str(path))

    sections = parse_docx(str(path))

    assert all(s.images == [] for s in sections)
