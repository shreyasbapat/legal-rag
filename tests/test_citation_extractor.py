from legal_rag.ingestion.citation_extractor import extract_citations


def test_extracts_air_citation() -> None:
    assert extract_citations("This was settled in AIR 1973 SC 1461.") == ["AIR 1973 SC 1461"]


def test_extracts_scc_citation_with_parens() -> None:
    assert extract_citations("See (1973) 4 SCC 225 for the majority view.") == ["(1973) 4 SCC 225"]


def test_extracts_scc_citation_without_parens() -> None:
    assert extract_citations("reported at 1973 4 SCC 225") == ["1973 4 SCC 225"]


def test_extracts_scr_citation() -> None:
    assert extract_citations("1973 SCR (1) 1 held that...") == ["1973 SCR (1) 1"]


def test_deduplicates_repeated_citations_preserving_order() -> None:
    text = "AIR 1973 SC 1461 ... later again AIR 1973 SC 1461, and also (1973) 4 SCC 225."
    assert extract_citations(text) == ["AIR 1973 SC 1461", "(1973) 4 SCC 225"]


def test_no_citations_returns_empty_list() -> None:
    assert extract_citations("No citations in this sentence at all.") == []


def test_normalizes_internal_whitespace() -> None:
    assert extract_citations("AIR   1973   SC   1461") == ["AIR 1973 SC 1461"]
