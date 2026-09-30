from pathlib import Path

from app.core.parsing.pdf_parser import PageUnit
from app.services.local_search import extract_text_from_file, is_image_file, scan_root, select_pdf_images


def test_extract_text_from_file_reads_plain_text(tmp_path: Path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text("Bonjour le monde\nContrat de travail\n", encoding="utf-8")

    text = extract_text_from_file(file_path)

    assert "Bonjour" in text
    assert "Contrat" in text


def test_scan_root_ignores_common_noise_directories(tmp_path: Path):
    keep_dir = tmp_path / "documents"
    keep_dir.mkdir()
    (keep_dir / "guide.md").write_text("Guide de migration Python\n", encoding="utf-8")

    ignore_dir = tmp_path / ".git"
    ignore_dir.mkdir()
    (ignore_dir / "config").write_text("secret", encoding="utf-8")

    cache_dir = tmp_path / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "cache.pyc").write_bytes(b"binary")

    files = scan_root(tmp_path, max_files=20)

    assert any(f["filename"] == "guide.md" for f in files)
    assert all(".git" not in str(f["path"]) for f in files)
    assert all("__pycache__" not in str(f["path"]) for f in files)


def test_scan_root_includes_images_for_visual_description(tmp_path: Path):
    from PIL import Image

    from app.config import settings

    settings.local_min_image_bytes = 0
    settings.local_min_image_side = 0
    image_path = tmp_path / "plage.jpg"
    Image.new("RGB", (400, 400), (10, 10, 250)).save(image_path)

    files = scan_root(tmp_path, max_files=20)

    assert is_image_file(image_path)
    assert any(item["filename"] == "plage.jpg" for item in files)


def test_select_pdf_images_dedupes_keeps_largest_and_page_order():
    logo = b"L" * 4000
    pages = [
        PageUnit(page_number=1, text="", images=[logo, b"a" * 9000]),
        PageUnit(page_number=2, text="", images=[logo, b"b" * 5000, b"c" * 20000]),
        PageUnit(page_number=3, text="", images=[logo]),
    ]

    selected = select_pdf_images(pages, limit=2)

    # le logo répété n'est compté qu'une fois ; les deux plus lourdes sont gardées, dans l'ordre des pages
    assert [(page, len(data)) for page, data in selected] == [(1, 9000), (2, 20000)]
    assert select_pdf_images(pages, limit=0) == []
