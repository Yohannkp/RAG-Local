def parse_txt(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()
