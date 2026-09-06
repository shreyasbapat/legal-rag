"""Splits judgment body text into paragraphs, preferring native paragraph numbering."""

from __future__ import annotations

import re
from dataclasses import dataclass

_NUMBERED_PARA_RE = re.compile(r"(?m)^[ \t]*(\d{1,4})\.[ \t]+")


@dataclass(frozen=True)
class ParsedParagraph:
    number: int | None
    text: str


class ParagraphParser:
    """Splits judgment body text into paragraphs.

    Indian judgments are conventionally numbered ("1.", "2.", ...) at the
    start of each substantive paragraph, and that numbering is exactly what
    advocates and later judgments cite ("see para 42"). We use it as the
    chunk boundary instead of a fixed token window whenever it's reliably
    present.

    A run of numbered matches is only trusted if the captured numbers
    strictly increase by 1 -- this rejects false positives such as an
    enumerated sub-clause ("3. and 4. above") appearing mid-paragraph and
    being mistaken for a paragraph break. If no run of at least
    ``min_sequential_matches`` is found, falls back to splitting on blank
    lines with no paragraph number assigned.
    """

    min_sequential_matches = 2

    def parse(self, text: str) -> list[ParsedParagraph]:
        text = text.strip("\n")
        if not text.strip():
            return []

        matches = list(_NUMBERED_PARA_RE.finditer(text))
        sequential = self._longest_sequential_run(matches)

        if len(sequential) >= self.min_sequential_matches:
            return self._split_on_matches(text, sequential)
        return self._split_on_blank_lines(text)

    @staticmethod
    def _longest_sequential_run(matches: list[re.Match[str]]) -> list[re.Match[str]]:
        """Return the longest run of matches whose captured numbers strictly increase by 1."""
        best: list[re.Match[str]] = []
        current: list[re.Match[str]] = []
        prev_num: int | None = None
        for m in matches:
            num = int(m.group(1))
            current = [*current, m] if prev_num is not None and num == prev_num + 1 else [m]
            prev_num = num
            if len(current) > len(best):
                best = current
        return best

    @staticmethod
    def _split_on_matches(text: str, matches: list[re.Match[str]]) -> list[ParsedParagraph]:
        paragraphs: list[ParsedParagraph] = []
        preamble = text[: matches[0].start()].strip()
        if preamble:
            paragraphs.append(ParsedParagraph(number=None, text=preamble))

        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            if body:
                paragraphs.append(ParsedParagraph(number=int(m.group(1)), text=body))
        return paragraphs

    @staticmethod
    def _split_on_blank_lines(text: str) -> list[ParsedParagraph]:
        chunks = re.split(r"\n\s*\n", text)
        return [
            ParsedParagraph(number=None, text=chunk.strip()) for chunk in chunks if chunk.strip()
        ]
