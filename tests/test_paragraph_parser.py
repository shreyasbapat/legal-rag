from legal_rag.ingestion.paragraph_parser import ParagraphParser


def test_splits_on_sequential_numbering() -> None:
    text = (
        "1. This is the first paragraph.\n\n"
        "2. This is the second paragraph.\n\n"
        "3. This is the third paragraph."
    )
    paragraphs = ParagraphParser().parse(text)
    assert [p.number for p in paragraphs] == [1, 2, 3]
    assert paragraphs[1].text == "This is the second paragraph."


def test_preamble_before_first_numbered_paragraph_is_kept_unnumbered() -> None:
    text = (
        "IN THE SUPREME COURT OF INDIA\n\n"
        "1. First substantive paragraph.\n\n"
        "2. Second substantive paragraph."
    )
    paragraphs = ParagraphParser().parse(text)
    assert paragraphs[0].number is None
    assert "SUPREME COURT" in paragraphs[0].text
    assert [p.number for p in paragraphs[1:]] == [1, 2]


def test_falls_back_to_blank_line_split_when_no_sequential_numbering() -> None:
    text = "First paragraph with no numbering.\n\nSecond paragraph."
    paragraphs = ParagraphParser().parse(text)
    assert len(paragraphs) == 2
    assert all(p.number is None for p in paragraphs)


def test_ignores_isolated_non_sequential_number_before_real_sequence() -> None:
    # "498." here reads like a statute section number, not a paragraph marker.
    # It must not derail detection of the genuine 1, 2, 3 sequence that follows.
    text = (
        "See Section 302 of the Code.\n\n"
        "498. Whoever commits an offence under this section shall be punished.\n\n"
        "1. This is truly the first paragraph of the judgment.\n\n"
        "2. This is the second.\n\n"
        "3. This is the third."
    )
    paragraphs = ParagraphParser().parse(text)
    assert [p.number for p in paragraphs[-3:]] == [1, 2, 3]
    assert "498." in paragraphs[0].text


def test_empty_text_returns_no_paragraphs() -> None:
    assert ParagraphParser().parse("   \n\n  ") == []
