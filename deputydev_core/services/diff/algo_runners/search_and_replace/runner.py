import difflib
import math
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from deputydev_core.services.diff.algo_runners.base_diff_algo_runner import BaseDiffAlgoRunner
from deputydev_core.services.diff.dataclasses.main import FileDiffApplicationResponse, SearchAndReplaceData


@dataclass
class EditError:
    original: str
    replacement: str
    message: str
    suggestions: List[str]


class SearchAndReplaceAlgoRunner(BaseDiffAlgoRunner):
    """Implements SEARCH/REPLACE diff algorithm with flexible matching strategies."""

    # ---------------------------------------------------------------------
    # Helpers ──────────────────────────────────────────────────────────────
    # ---------------------------------------------------------------------
    @classmethod
    def _prep_with_trailing(cls, content: str) -> Tuple[str, List[str], str, bool]:
        """Like prep(), but also returns whether the original file had a trailing newline."""
        # Detect the dominant EOL style *once* so we can re‑emit later.
        newline_style = "\r\n" if "\r\n" in content else "\n"

        # Detect if original had a trailing newline at all
        had_trailing_newline = content.endswith(("\r\n", "\n"))

        # Internal representation always uses LF only.
        content_lf = content.replace("\r\n", "\n")

        # Guarantee trailing newline so line‑based offsets are simpler.
        if content_lf and not content_lf.endswith("\n"):
            content_lf += "\n"

        lines = content_lf.splitlines(keepends=True)
        return content_lf, lines, newline_style, had_trailing_newline

    @classmethod
    def prep(cls, content: str) -> Tuple[str, List[str], str]:
        """Normalise new-lines to **LF**, ensure trailing LF, split into lines.

        Returns a 3-tuple: *(normalised_content, lines_with_endings, original_eol)*.
        """
        content_lf, lines, newline_style, _ = cls._prep_with_trailing(content)
        return content_lf, lines, newline_style

    # Add this staticmethod to your class:
    @staticmethod
    def trim_blank_lines(lines: List[str]) -> List[str]:
        start, end = 0, len(lines)
        while start < end and not lines[start].strip():
            start += 1
        while end > start and not lines[end - 1].strip():
            end -= 1
        return lines[start:end]

    # ------------------------------------------------------------------
    # Exact / flexible matching strategies
    # ------------------------------------------------------------------

    @classmethod
    def perfect_replace(cls, whole_lines: List[str], part_lines: List[str]) -> Optional[int]:
        """Return starting index of a perfect *line‑wise* match, ignoring leading/trailing blanks."""
        part_lines = cls.trim_blank_lines(part_lines)
        part_len = len(part_lines)
        for i in range(len(whole_lines) - part_len + 1):
            window = cls.trim_blank_lines(whole_lines[i : i + part_len])
            if window == part_lines:
                return i
        return None

    @classmethod
    def match_but_for_leading_whitespace(cls, whole_chunk: List[str], part_lines: List[str]) -> Optional[str]:
        """If chunks match after stripping *uniform* indent, return that indent prefix."""
        for w, p in zip(whole_chunk, part_lines):
            if w.lstrip() != p.lstrip():
                return None
        prefixes = {w[: len(w) - len(p)] for w, p in zip(whole_chunk, part_lines) if p.strip()}
        return prefixes.pop() if len(prefixes) == 1 else None

    @classmethod
    def find_indent_flexible(cls, whole_lines: List[str], part_lines: List[str]) -> Optional[int]:
        """Find block allowing uniform indent delta, ignoring leading/trailing blanks."""
        part_lines = cls.trim_blank_lines(part_lines)
        part_len = len(part_lines)
        for i in range(len(whole_lines) - part_len + 1):
            window = cls.trim_blank_lines(whole_lines[i : i + part_len])
            if len(window) != part_len:
                continue
            prefix = cls.match_but_for_leading_whitespace(window, part_lines)
            if prefix is not None:
                return i
        return None

    @classmethod
    def anchor_line_match(cls, whole_lines: List[str], part_lines: List[str]) -> Optional[int]:
        """If ≥3 lines: match by .strip() equality on first and last lines (block anchor), ignoring blank edges."""
        part_lines = cls.trim_blank_lines(part_lines)
        if len(part_lines) < 3:
            return None
        first, last = part_lines[0].strip(), part_lines[-1].strip()
        size = len(part_lines)
        for i in range(len(whole_lines) - size + 1):
            window = cls.trim_blank_lines(whole_lines[i : i + size])
            if len(window) != size:
                continue
            if window[0].strip() == first and window[-1].strip() == last:
                return i
        return None

    # ──────────────────────────────────────────────────────────────────
    # NEW ❶  ─ Whitespace‑trimmed exact match
    # ──────────────────────────────────────────────────────────────────
    @classmethod
    def line_trimmed_match(cls, whole_lines: List[str], part_lines: List[str]) -> Optional[int]:
        """Exact equality after .strip() on each corresponding line, ignoring blank edges."""
        part_lines = cls.trim_blank_lines(part_lines)
        part_len = len(part_lines)
        for i in range(len(whole_lines) - part_len + 1):
            window = cls.trim_blank_lines(whole_lines[i : i + part_len])
            if len(window) != part_len:
                continue
            if all(window[j].strip() == part_lines[j].strip() for j in range(part_len)):
                return i
        return None

    # ------------------------------------------------------------------
    # Fuzzy helpers (unchanged)
    # ------------------------------------------------------------------

    @classmethod
    def replace_closest_edit_distance(
        cls, whole_lines: List[str], part: str, part_lines: List[str]
    ) -> Optional[Tuple[int, int]]:
        """Return (start_line, end_line) of the best fuzzy window above threshold."""
        threshold = 0.8
        best_ratio = 0.0
        best_span = (0, 0)
        target_len = len(part_lines)
        min_len = max(1, math.floor(target_len * 0.9))
        max_len = math.ceil(target_len * 1.1)

        for length in range(min_len, max_len + 1):
            for i in range(len(whole_lines) - length + 1):
                chunk = "".join(whole_lines[i : i + length])
                ratio = difflib.SequenceMatcher(None, chunk, part).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_span = (i, i + length)
        if best_ratio < threshold:
            return None
        return best_span

    # ------------------------------------------------------------------
    # Span location orchestrator
    # ------------------------------------------------------------------
    @classmethod
    def locate_span(cls, whole: str, part: str) -> Optional[Tuple[int, int]]:
        """Return *(start_char, end_char)* of *part* inside *whole* using layered fallbacks."""
        # Normalise both strings once.
        whole_norm, whole_lines, _ = cls.prep(whole)
        part_norm, part_lines, _ = cls.prep(part)

        # 1️⃣  Exact substring
        exact_pos = whole_norm.find(part_norm)
        if exact_pos != -1:
            return exact_pos, exact_pos + len(part_norm)

        # 2️⃣  Indent‑flexible line match
        idx = cls.find_indent_flexible(whole_lines, part_lines)
        if idx is not None:
            start = sum(len(line) for line in whole_lines[:idx])
            end = start + sum(len(line) for line in whole_lines[idx : idx + len(part_lines)])
            return start, end

        # 3️⃣  NEW whitespace‑trimmed line match
        idx = cls.line_trimmed_match(whole_lines, part_lines)
        if idx is not None:
            start = sum(len(line) for line in whole_lines[:idx])
            end = start + sum(len(line) for line in whole_lines[idx : idx + len(part_lines)])
            return start, end

        # 4️⃣  NEW: Block-anchor fallback
        idx = cls.anchor_line_match(whole_lines, part_lines)
        if idx is not None:
            start = sum(len(line) for line in whole_lines[:idx])
            end = start + sum(len(line) for line in whole_lines[idx : idx + len(part_lines)])
            return start, end

        # 4️⃣  Fuzzy (edit distance)
        span = cls.replace_closest_edit_distance(whole_lines, part_norm, part_lines)
        if span is not None:
            i, j = span
            start = sum(len(line) for line in whole_lines[:i])
            end = start + sum(len(line) for line in whole_lines[i:j])
            return start, end

        return None

    # ------------------------------------------------------------------
    # Suggestion helper (unchanged)
    # ------------------------------------------------------------------

    @classmethod
    def find_similar_lines(cls, search_lines: str, content: str, threshold: float = 0.6) -> str:
        """Return a best‑guess context snippet for a failed SEARCH block."""
        needles = search_lines.splitlines()
        hay = content.splitlines()
        best_ratio = 0.0
        best_ctx: Tuple[int, List[str]] = (0, [])
        L = len(needles)  # noqa: N806
        for i in range(len(hay) - L + 1):
            chunk = hay[i : i + L]
            ratio = difflib.SequenceMatcher(None, needles, chunk).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_ctx = (i, chunk)
        if best_ratio < threshold:
            return ""
        start, chunk = best_ctx
        before = max(0, start - 3)
        after = min(len(hay), start + L + 3)
        return "\n".join(hay[before:after])

    # ------------------------------------------------------------------
    # Parse SEARCH / REPLACE blocks (unchanged)
    # ------------------------------------------------------------------
    @classmethod
    def _extract_search_replace_blocks(cls, blocks_text: str) -> List[Tuple[str, str]]:
        HEAD = re.compile(r"^[-]{3,} SEARCH\s*$")  # noqa: N806
        DIV = re.compile(r"^[=]{3,}\s*$")  # noqa: N806
        UPD = re.compile(r"^[+]{3,} REPLACE\s*$")  # noqa: N806

        lines = blocks_text.splitlines(keepends=True)
        i, n = 0, len(lines)
        edits: List[Tuple[str, str]] = []
        while i < n:
            if HEAD.match(lines[i].strip()):
                i += 1
                orig_buf: List[str] = []
                while i < n and not DIV.match(lines[i].strip()):
                    orig_buf.append(lines[i])
                    i += 1
                if i >= n or not DIV.match(lines[i].strip()):
                    raise ValueError("Unterminated SEARCH block (no =======)")
                i += 1
                repl_buf: List[str] = []
                while i < n and not UPD.match(lines[i].strip()):
                    repl_buf.append(lines[i])
                    i += 1
                if i >= n or not UPD.match(lines[i].strip()):
                    raise ValueError("Unterminated REPLACE block (no +++++++ REPLACE)")
                i += 1
                edits.append(("".join(orig_buf), "".join(repl_buf)))
            else:
                i += 1
        return edits

    @classmethod
    async def apply_diff(  # noqa: C901
        cls, file_path: str, repo_path: str, current_content: str, diff_data: SearchAndReplaceData
    ) -> FileDiffApplicationResponse:
        # ① Normalise current file once (track if original had a trailing newline)
        current_norm, _, newline_style, had_trailing_newline = cls._prep_with_trailing(current_content)

        # Flag (default True; change as needed)
        preserve_trailing_newline = getattr(diff_data, "preserve_trailing_newline", True)

        blocks_text = diff_data.search_and_replace_blocks
        edits = cls._extract_search_replace_blocks(blocks_text)

        errors: List[EditError] = []
        matches: List[Tuple[int, int, str]] = []  # (start, end, replacement)

        # User sent something, but we couldn't parse any valid blocks
        if blocks_text and blocks_text.strip() and not edits:
            raise ValueError(
                "SEARCH/REPLACE text was provided, but no well-formed blocks were parsed.\n"
                "Expected:\n"
                "  ------- SEARCH\n"
                "  ...original content...\n"
                "  =======\n"
                "  ...replacement content...\n"
                "  +++++++ REPLACE"
            )

        # Pass 1: locate each SEARCH block
        for idx, (orig, repl) in enumerate(edits, start=1):
            if not orig.strip():  # empty SEARCH ⇒ append at EOF
                matches.append((len(current_norm), len(current_norm), repl))
                continue

            span = cls.locate_span(current_norm, orig)

            if span is None:
                suggestion = cls.find_similar_lines(orig, current_norm)
                errors.append(
                    EditError(
                        original=orig,
                        replacement=repl,
                        message=f"Edit #{idx} failed to match any block in the file.",
                        suggestions=suggestion.splitlines() if suggestion else [],
                    )
                )
            else:
                start, end = span
                matches.append((start, end, repl))

        if errors:
            err_msgs = []
            for e in errors:
                msg = (
                    "===== FAILED EDIT =====\n"
                    f"Original:\n```\n{e.original.strip()}\n```\n\n"
                    f"Replacement:\n```\n{e.replacement.strip()}\n```\n\n"
                    f"Message: {e.message}"
                )
                if e.suggestions:
                    msg += "\n\nSuggestions:\n```\n" + "\n".join(e.suggestions) + "\n```"
                err_msgs.append(msg)
            raise ValueError("\n\n".join(err_msgs))

        # Pass 2: sort + check overlap
        matches.sort(key=lambda t: t[0])
        for (s1, e1, _), (s2, _, _) in zip(matches, matches[1:]):
            if s2 < e1:
                raise ValueError(
                    "SEARCH/REPLACE blocks overlap. Please retry and make them non‑overlapping or merge them."
                )

        # Pass 3: apply edits to the normalised text
        pieces: List[str] = []
        cursor = 0
        for start, end, repl in matches:
            pieces.append(current_norm[cursor:start])
            pieces.append(repl)
            cursor = end
        pieces.append(current_norm[cursor:])

        new_norm = "".join(pieces)

        # === Trailing newline fix START ===
        # Internally we forced a trailing \n; if original had none and user wants to preserve that,
        # then strip it back off before converting CRLF if necessary.
        if preserve_trailing_newline and not had_trailing_newline and new_norm.endswith("\n"):
            new_norm = new_norm[:-1]

        # Restore original newline style
        if newline_style == "\n":
            new_content = new_norm
        else:
            new_content = new_norm.replace("\n", "\r\n")
            if preserve_trailing_newline and not had_trailing_newline and new_content.endswith("\r\n"):
                new_content = new_content[:-2]
        # === Trailing newline fix END ===

        final_file_contents: dict[str, str] = {}
        if new_content != current_content:
            final_file_contents[file_path] = new_content

        # We had a non-empty request, but ended up with no modified content
        user_supplied_blocks = bool(blocks_text and blocks_text.strip())
        if user_supplied_blocks and not final_file_contents:
            raise ValueError(
                "SEARCH/REPLACE request was provided, but it produced no modified content. "
                "Either nothing matched, replacements were identical, or the delimiters were malformed. Please read the file with iterative file reader to check latest content.\n"
            )

        return FileDiffApplicationResponse(
            new_file_path=file_path,
            new_content=final_file_contents.get(file_path, ""),
        )
