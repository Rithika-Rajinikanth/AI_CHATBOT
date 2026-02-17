"""
agents/contract_compare.py
Compares two lists of document chunks and returns per-chunk diffs.
"""


def compare(contract_a: list, contract_b: list) -> list:
    """
    Returns:
        List of dicts: {chunk_index, source_a, source_b, text_a, text_b}
    """
    diffs   = []
    min_len = min(len(contract_a), len(contract_b))

    for i in range(min_len):
        a, b = contract_a[i], contract_b[i]
        if a.page_content.strip() != b.page_content.strip():
            diffs.append({
                "chunk_index": i,
                "source_a":    a.metadata.get("source", "Doc A"),
                "source_b":    b.metadata.get("source", "Doc B"),
                "text_a":      a.page_content.strip(),
                "text_b":      b.page_content.strip(),
            })

    # Extra chunks in the longer document
    for i in range(min_len, len(contract_a)):
        diffs.append({
            "chunk_index": i,
            "source_a":    contract_a[i].metadata.get("source", "Doc A"),
            "source_b":    "—",
            "text_a":      contract_a[i].page_content.strip(),
            "text_b":      "[No matching chunk in Doc B]",
        })
    for i in range(min_len, len(contract_b)):
        diffs.append({
            "chunk_index": i,
            "source_a":    "—",
            "source_b":    contract_b[i].metadata.get("source", "Doc B"),
            "text_a":      "[No matching chunk in Doc A]",
            "text_b":      contract_b[i].page_content.strip(),
        })

    return diffs
