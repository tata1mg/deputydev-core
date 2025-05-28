import re
import difflib
import math
from dataclasses import dataclass
from typing import List, Tuple, Optional

from deputydev_core.services.diff.algo_runners.base_diff_algo_runner import BaseDiffAlgoRunner
from deputydev_core.services.diff.dataclasses.main import FileDiffApplicationResponse, SearchAndReplaceData


@dataclass
class EditError:
    original: str
    replacement: str
    message: str
    suggestions: List[str]


class SearchAndReplaceAlgoRunner(BaseDiffAlgoRunner):
    @classmethod
    def prep(cls, content: str) -> Tuple[str, List[str]]:
        """
        Ensure content ends with a newline, then split into lines (with endings).
        """
        if content and not content.endswith("\n"):
            content += "\n"
        lines = content.splitlines(keepends=True)
        return content, lines

    @classmethod
    def perfect_replace(cls, whole_lines: List[str], part_lines: List[str], replace_lines: List[str]) -> Optional[str]:
        """
        Exact match of part_lines in whole_lines and replace in one shot.
        """
        part_tup = tuple(part_lines)
        part_len = len(part_lines)
        for i in range(len(whole_lines) - part_len + 1):
            if tuple(whole_lines[i : i + part_len]) == part_tup:
                combined = whole_lines[:i] + replace_lines + whole_lines[i + part_len :]
                return "".join(combined)
        return None

    @classmethod
    def match_but_for_leading_whitespace(cls, whole_chunk: List[str], part_lines: List[str]) -> Optional[str]:
        """
        If part_lines match whole_chunk modulo a uniform indent, return that indent prefix.
        """
        for w, p in zip(whole_chunk, part_lines):
            if w.lstrip() != p.lstrip():
                return None
        prefixes = {w[: len(w) - len(p)] for w, p in zip(whole_chunk, part_lines) if p.strip()}
        if len(prefixes) == 1:
            return prefixes.pop()
        return None

    @classmethod
    def replace_part_with_missing_leading_whitespace(
        cls, whole_lines: List[str], part_lines: List[str], replace_lines: List[str]
    ) -> Optional[str]:
        """
        Match part_lines allowing for uniform indent differences, re-indent replace_lines accordingly.
        """
        indents = [
            len(line) - len(line.lstrip()) for block in (part_lines, replace_lines) for line in block if line.strip()
        ]
        if indents and min(indents) > 0:
            trim = min(indents)
            part_lines = [line[trim:] if line.strip() else line for line in part_lines]
            replace_lines = [line[trim:] if line.strip() else line for line in replace_lines]

        part_len = len(part_lines)
        for i in range(len(whole_lines) - part_len + 1):
            prefix = cls.match_but_for_leading_whitespace(whole_lines[i : i + part_len], part_lines)
            if prefix is None:
                continue
            reindented = [(prefix + rl) if rl.strip() else rl for rl in replace_lines]
            new = whole_lines[:i] + reindented + whole_lines[i + part_len :]
            return "".join(new)
        return None

    @classmethod
    def try_dotdotdots(cls, whole: str, part: str, replace: str) -> Optional[str]:
        """
        Handle blocks containing '...' by splitting on them and replacing each chunk.
        """
        dots_re = re.compile(r"(^\s*\.\.\.\n)", re.MULTILINE)
        part_pieces = re.split(dots_re, part)
        replace_pieces = re.split(dots_re, replace)
        if len(part_pieces) != len(replace_pieces) or len(part_pieces) < 3:
            return None
        for idx in range(1, len(part_pieces), 2):
            if part_pieces[idx] != replace_pieces[idx]:
                return None
        result = whole
        for p_chunk, r_chunk in zip(part_pieces[::2], replace_pieces[::2]):
            if not p_chunk:
                if not result.endswith("\n"):
                    result += "\n"
                result += r_chunk
            else:
                if result.count(p_chunk) != 1:
                    return None
                result = result.replace(p_chunk, r_chunk, 1)
        return result

    @classmethod
    def replace_closest_edit_distance(
        cls, whole_lines: List[str], part: str, part_lines: List[str], replace_lines: List[str]
    ) -> Optional[str]:
        """
        Fallback: pick chunk with highest SequenceMatcher ratio above threshold.
        """
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
        i, j = best_span
        updated = whole_lines[:i] + replace_lines + whole_lines[j:]
        return "".join(updated)

    @classmethod
    def replace_most_similar_chunk(cls, whole: str, part: str, replace: str) -> Optional[str]:
        """
        Try exact, whitespace-flexible, dots-aware, then fuzzy replacement.
        """
        whole, whole_lines = cls.prep(whole)
        part, part_lines = cls.prep(part)
        replace, replace_lines = cls.prep(replace)

        res = cls.perfect_replace(whole_lines, part_lines, replace_lines)
        if res is not None:
            return res
        res = cls.replace_part_with_missing_leading_whitespace(whole_lines, part_lines, replace_lines)
        if res is not None:
            return res
        res = cls.try_dotdotdots(whole, part, replace)
        if res is not None:
            return res
        return cls.replace_closest_edit_distance(whole_lines, part, part_lines, replace_lines)

    @classmethod
    def do_replace(cls, content: str, before_text: str, after_text: str) -> Optional[str]:
        """
        Perform one search/replace block on `content`.
        """
        if not before_text.strip():
            return content + after_text
        return cls.replace_most_similar_chunk(content, before_text, after_text)

    @classmethod
    def find_similar_lines(cls, search_lines: str, content: str, threshold: float = 0.6) -> str:
        """
        Suggest the most similar region in content for a failed block.
        """
        needles = search_lines.splitlines()
        hay = content.splitlines()
        best_ratio = 0.0
        best_ctx: Tuple[int, List[str]] = (0, [])
        L = len(needles)
        for i in range(len(hay) - L + 1):
            chunk = hay[i : i + L]
            ratio = difflib.SequenceMatcher(None, needles, chunk).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_ctx = (i, chunk)
        if best_ratio < threshold:
            return ""
        start, chunk = best_ctx
        if chunk[0] == needles[0] and chunk[-1] == needles[-1]:
            return "\n".join(chunk)
        before = max(0, start - 3)
        after = min(len(hay), start + L + 3)
        return "\n".join(hay[before:after])

    @classmethod
    def _extract_search_replace_blocks(cls, blocks_text: str) -> List[Tuple[str, str]]:
        """
        Parse all SEARCH/REPLACE blocks, returning a list of (original, replacement).
        """
        HEAD = re.compile(r"^<<<<<<< SEARCH\s*$")
        DIV = re.compile(r"^=======$")
        UPD = re.compile(r"^>>>>>>> REPLACE\s*$")

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
                    raise ValueError("Unterminated REPLACE block (no >>>>>>> REPLACE)")
                i += 1
                edits.append(("".join(orig_buf), "".join(repl_buf)))
            else:
                i += 1
        return edits

    @classmethod
    async def apply_diff(
        cls, file_path: str, repo_path: str, current_content: str, diff_data: SearchAndReplaceData
    ) -> FileDiffApplicationResponse:
        """
        Apply search-and-replace blocks to in-memory content.
        """
        final_file_contents: dict[str, str] = {}
        errors: List[EditError] = []

        blocks_text = diff_data.search_and_replace_blocks
        edits = cls._extract_search_replace_blocks(blocks_text)
        content = current_content

        for idx, (orig, repl) in enumerate(edits, start=1):
            new_content = cls.do_replace(content, orig, repl)
            if new_content is None:
                suggestion = cls.find_similar_lines(orig, content)
                suggestions = suggestion.splitlines() if suggestion else []
                errors.append(
                    EditError(
                        original=orig,
                        replacement=repl,
                        message=f"Edit #{idx} failed to match any block in the file.",
                        suggestions=suggestions,
                    )
                )
            else:
                content = new_content

        if content != current_content:
            final_file_contents[file_path] = content

        if errors:
            formatted_errors = []
            for error in errors:
                block = (
                    f"===== FAILED EDIT =====\n"
                    f"Original:\n```\n{error.original.strip()}\n```\n\n"
                    f"Replacement:\n```\n{error.replacement.strip()}\n```\n\n"
                    f"Message:\n{error.message}"
                )
                if error.suggestions:
                    block += "\n\nSuggestions:\n```\n" + "\n".join(error.suggestions) + "\n```"
                formatted_errors.append(block)
            raise ValueError("\n\n".join(formatted_errors))

        return FileDiffApplicationResponse(new_file_path=file_path, new_content=final_file_contents.get(file_path, ""))
