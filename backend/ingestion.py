"""Ingestion: TXT -> passages -> vectors -> database."""
from .retrieval import EMBED_MODEL, embedding
from .storage import save_document
MAX_UPLOAD = 8 * 1024 * 1024
def read_text(data):
    text = data.decode("utf-8-sig")
    lines = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if line.strip():
            lines.append((line, f"Line {line_number}"))
    return lines
def chunk(records):
    result, text, references = [], "", []
    for value, ref in records:
        if text and (value.strip() == "---" or len(text) + len(value) > 700):
            result.append((text, ", ".join(references)))
            text, references = "", []
        if value.strip() == "---":
            continue
        text = (text + "\n" + value).strip()
        references.append(ref)
    if text:
        result.append((text, ", ".join(references)))
    return result
def ingest(filename, data):
    # Read the TXT file, split it, and turn each passage into numbers.
    passages = chunk(read_text(data))
    if not passages:
        raise ValueError("No readable text was found in this file.")
    vectors = []
    for text, reference in passages:
        vectors.append(embedding(f"{filename}\n{text}"))
    return save_document(filename, data, passages, vectors, EMBED_MODEL)
