from dataclasses import dataclass, field

from pypdf import PdfReader

# En dessous de ce poids, une image est presque toujours une icone/puce
# decorative plutot qu'un contenu porteur d'info (photo, graphique, scan).
_MIN_MEANINGFUL_IMAGE_BYTES = 3000


@dataclass
class PageUnit:
    page_number: int
    text: str
    images: list[bytes] = field(default_factory=list)


def parse_pdf(path: str) -> list[PageUnit]:
    reader = PdfReader(path)
    units: list[PageUnit] = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        images = [
            img.data
            for img in page.images
            if len(img.data) >= _MIN_MEANINGFUL_IMAGE_BYTES
        ]
        units.append(PageUnit(page_number=i, text=text, images=images))
    return units


def find_empty_pages(units: list[PageUnit]) -> list[int]:
    """Pages sans texte extractible : probablement une image, un scan, ou un
    tableau/graphique complexe que pypdf ne sait pas lire. Detecte aussi bien
    un document entierement scanne qu'une seule page image au milieu d'un
    document sinon normal (ex: une annexe scannee)."""
    return [u.page_number for u in units if len(u.text) < 20]
