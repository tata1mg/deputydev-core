import difflib
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from deputydev_core.services.diff.algo_runners.base_diff_algo_runner import (
    BaseDiffAlgoRunner,
)
from deputydev_core.services.diff.dataclasses.main import (
    FileDiffApplicationResponse,
    UdiffData,
)

from .search_and_replace import (
    SearchTextNotUnique,
    all_preprocs,
    diff_lines,
    flexible_search_and_replace,
    search_and_replace,
)

NO_MATCH_ERROR = """UnifiedDiffNoMatch: edit failed to apply!

{path} does not contain lines that match the diff you provided!
Try again.
DO NOT skip blank lines, comments, docstrings, etc!
The diff needs to apply cleanly to the lines in {path}!

{path} does not contain these {num_lines} exact lines in a row:
```
{original}```
"""


NOT_UNIQUE_ERROR = """UnifiedDiffNotUnique: edit failed to apply!

{path} contains multiple sets of lines that match the diff you provided!
Try again.
Use additional ` ` lines to provide context that uniquely indicates which code needs to be changed.
The diff needs to apply to a unique set of lines in {path}!

{path} contains multiple copies of these {num_lines} lines:
```
{original}```
"""


class UnifiedDiffAlgoRunner(BaseDiffAlgoRunner):
    @classmethod
    def _flexi_just_search_and_replace(cls, texts: List[str]) -> Optional[str]:
        strategies = [
            (search_and_replace, all_preprocs),
        ]

        return flexible_search_and_replace(texts, strategies)

    @classmethod
    def _directly_apply_hunk(cls, content: str, hunk: List[str]) -> Optional[str]:
        before_texts, after_texts = cls._hunk_to_before_after(hunk)
        before, after = "".join(before_texts).rstrip("\r\n"), "".join(after_texts).rstrip("\r\n")

        # if the before text is not in the content, we cannot apply the diff
        if not before:
            return None

        before_lines, _ = cls._hunk_to_before_after(hunk)

        # get sanitized before text
        before_lines = "".join([line.strip() for line in before_lines])

        # do not do a repeated search and replace on a tiny bit of non-whitespace context
        # this is a heuristic to avoid doing a search and replace on a small amount of context
        if len(before_lines) < 10 and content.count(before) > 1:
            return None

        try:
            new_content = cls._flexi_just_search_and_replace([before, after, content])
        except SearchTextNotUnique:
            new_content = None

        return new_content

    @classmethod
    def _apply_partial_hunk(
        cls,
        content: str,
        preceding_context: List[str],
        changes: List[str],
        following_context: List[str],
    ) -> Optional[str]:
        """
        Apply a partial hunk to the content
        """
        len_prec = len(preceding_context)
        len_foll = len(following_context)

        use_all = len_prec + len_foll

        # if there is a - in the hunk, we can go all the way to `use=0`
        for drop in range(use_all + 1):
            use = use_all - drop

            for use_prec in range(len_prec, -1, -1):
                if use_prec > use:
                    continue

                use_foll = use - use_prec
                if use_foll > len_foll:
                    continue

                if use_prec:
                    this_prec = preceding_context[-use_prec:]
                else:
                    this_prec = []

                this_foll = following_context[:use_foll]

                res = cls._directly_apply_hunk(content, this_prec + changes + this_foll)
                if res:
                    return res

    @classmethod
    def _process_fenced_block(cls, block: List[str]) -> List[List[str]]:
        """
        Cut a fenced block into hunks, hunks are basically a list of lines that have one contiguous change between them
        """
        # add a end of diff marker, will help us to cut the last diff
        block.append("@@ @@")

        # search for the diff start marker, and if there is newline before it, we want strip it
        for i in range(len(block)):
            if block[i].startswith("--- ") and block[i + 1].startswith("+++ "):
                block = block[i + 2 :]
                break

        edits: List[List[str]] = []

        keeper = False  # denotes if we want to keep the hunk, if we find a + or - we want to keep the line
        hunk: List[str] = []
        op = " "
        for line in block:
            hunk.append(line)
            if len(line) < 2:
                continue

            op = line[0]

            # if we find a + or - we want to keep the line, we
            if op in "-+":
                keeper = True
                continue
            if op != "@":
                continue

            # if we do not get any keeper lines, we do not want to keep the hunk
            if not keeper:
                hunk = []
                continue

            hunk = hunk[:-1]
            edits.append(hunk)
            hunk = []
            keeper = False

        return edits

    @classmethod
    def _get_edits(cls, file_path: str, incremental_udiff: str) -> List[List[str]]:
        # ensure the diff ends with a newline
        if not incremental_udiff.endswith("\n"):
            incremental_udiff += "\n"

        # Split the diff into lines
        diff_lines = incremental_udiff.splitlines(keepends=True)
        return cls._process_fenced_block(block=diff_lines)

    @classmethod
    def _hunk_to_before_after(cls, hunk: List[str]) -> Tuple[List[str], List[str]]:
        """
        Convert a hunk into a before and after list of lines

        Args:
            hunk: A list of lines in the hunk

        Returns:
            A tuple containing the before and after lists of lines
        """
        before: List[str] = []
        after: List[str] = []
        op: str = " "
        for line in hunk:
            if len(line) < 2:
                op = " "
                line = line
            else:
                op = line[0]
                line = line[1:]

            if op == " ":
                before.append(line)
                after.append(line)
            elif op == "-":
                before.append(line)
            elif op == "+":
                after.append(line)

        return before, after

    @classmethod
    def _cleanup_pure_whitespace_lines(cls, lines: List[str]) -> List[str]:
        """
        Remove any leading or trailing whitespace lines
        """
        res = [line if line.strip() else line[-(len(line) - len(line.rstrip("\r\n")))] for line in lines]
        return res

    @classmethod
    def _normalize_hunk(cls, hunk: List[str]) -> List[str]:
        """
        Normalize a hunk by removing any leading or trailing whitespace lines

        Args:
            hunk: A list of lines in the hunk
        """
        # get before and after lines
        before, after = cls._hunk_to_before_after(hunk)

        # remove leading and trailing whitespace lines
        before = cls._cleanup_pure_whitespace_lines(before)
        after = cls._cleanup_pure_whitespace_lines(after)

        # get the difflib diff as LLM format can be slightly different, so we basically get a purely applicable diff
        diff = difflib.unified_diff(before, after, n=max(len(before), len(after)))

        # remove the first 2 lines as they are just the file paths
        diff = list(diff)[3:]

        endline_normalized_diff: List[str] = []
        for _line in diff:
            endline_normalized_diff.append(_line.rstrip("\r\n") + "\n")
        return endline_normalized_diff

    @classmethod
    def _make_new_lines_explicit(cls, content: str, hunk: List[str]) -> List[str]:
        before_texts, after_texts = cls._hunk_to_before_after(hunk)
        before, after = "".join(before_texts), "".join(after_texts)

        diff: List[str] = diff_lines(before, content)

        back_diff: List[str] = []
        for line in diff:
            if line[0] == "+":
                continue
            # if line[0] == "-":
            #    line = "+" + line[1:]

            back_diff.append(line)

        new_before = cls._directly_apply_hunk(before, back_diff)

        # if we cannot apply the diff, we just return the original hunk
        if not new_before:
            return hunk

        # if the new before is less than 10 characters, we do not want to use it
        if len(new_before.strip()) < 10:
            return hunk

        before = before.splitlines(keepends=True)
        new_before = new_before.splitlines(keepends=True)
        after = after.splitlines(keepends=True)

        # if the new before is less than 2/3 of the original before, we do not want to use it
        if len(new_before) < len(before) * 0.66:
            return hunk

        # if the new before is more than 2/3 of original before, we want to use it
        new_hunk = difflib.unified_diff(new_before, after, n=max(len(new_before), len(after)))
        new_hunk = list(new_hunk)[3:]

        return new_hunk

    @classmethod
    def apply_hunk(cls, content: str, hunk: List[str]) -> Optional[str]:
        # before_text, after_text = cls._hunk_to_before_after(hunk)

        res = cls._directly_apply_hunk(content, hunk)
        if res:
            return res

        hunk = cls._make_new_lines_explicit(content, hunk)

        # just consider space vs not-space
        ops = "".join([line[0] for line in hunk])
        ops = ops.replace("-", "x")
        ops = ops.replace("+", "x")
        ops = ops.replace("\n", " ")

        cur_op = " "
        section: List[str] = []
        sections: List[List[str]] = []

        # split the hunk into sections based on the operation
        # operation is either " " or "x"
        # we just want to consider the space vs not-space operation
        for i in range(len(ops)):
            op = ops[i]
            if op != cur_op:
                sections.append(section)
                section = []
                cur_op = op
            section.append(hunk[i])

        sections.append(section)
        if cur_op != " ":
            sections.append([])

        all_done = True
        for i in range(2, len(sections), 2):
            preceding_context = sections[i - 2]
            changes = sections[i - 1]
            following_context = sections[i]

            res = cls._apply_partial_hunk(content, preceding_context, changes, following_context)
            if res:
                content = res
            else:
                all_done = False
                # FAILED!
                # this_hunk = preceding_context + changes + following_context
                break

        if all_done:
            return content

    @classmethod
    def do_replace(cls, file_path_str: str, content: Optional[str], hunk: List[str]) -> Optional[str]:

        # get the file path as a Path object
        file_path = Path(file_path_str)
        before_texts, after_texts = cls._hunk_to_before_after(hunk)
        before_text, after_text = "".join(before_texts), "".join(after_texts)

        # if the file does not exist and there is no before text, we can just create the file
        if not file_path.exists() and not before_text.strip():
            # file_path.touch()
            content = ""

        if not file_path.exists() and before_text.strip():
            before_text = ""
            content = ""

        # if the file does not exist and there is before text, we cannot apply the diff
        # this seems the case that when diff was generated, the file was present but now it is not
        if content is None:
            return None

        # TODO: handle inserting into new file

        # if there is no before text, we can just append the after text to the content
        if not before_text.strip():
            # append to existing file, or start a new file
            new_content = content + after_text
            return new_content

        new_content: Optional[str] = None
        new_content = cls.apply_hunk(content, hunk)
        if new_content:
            return new_content
        return None

    @classmethod
    def _normalize_endlines_content(cls, content: str) -> str:
        """
        Normalize the endline characters in the content
        """
        content_lines = content.splitlines(keepends=True)
        content_lines = [line.rstrip("\r\n") + "\n" for line in content_lines]
        return "".join(content_lines)

    @classmethod
    def _get_unique_normalized_edits(cls, edits: List[List[str]]) -> List[List[str]]:
        """
        Get the unique edits from the list of edits
        """
        seen: Set[str] = set()
        unique_edits: List[List[str]] = []
        for edit in edits:
            edit = cls._normalize_hunk(edit)
            if not edit:
                continue

            this = "".join(edit)
            if this in seen:
                continue
            seen.add(this)

            unique_edits.append(edit)

        return unique_edits

    @classmethod
    async def apply_diff(
        cls, file_path: str, repo_path: str, current_content: str, diff_data: UdiffData
    ) -> FileDiffApplicationResponse:
        """
        Apply the diff to the file.
        Args:
            file_path: The path to the file to apply the diff to
            repo_path: The path to the repository
            current_content: The current content of the file
            diff_data: The diff data to apply

        Returns:
            A FileDiffApplicationResponse object containing the new file path and content
        """

        final_file_contents: Dict[str, str] = {}
        errors: List[str] = []

        # firstly, get the unique hunks
        edits = cls._get_edits(file_path, diff_data.incremental_udiff)

        for file_edits in edits:
            unique_normalized_edits: List[List[str]] = cls._get_unique_normalized_edits(file_edits)
            full_path = os.path.join(repo_path, file_path)
            original_content: Optional[str] = current_content if current_content else None
            running_content: Optional[str] = original_content
            if running_content is not None:
                running_content = cls._normalize_endlines_content(running_content)

            for edit in unique_normalized_edits:
                original_lines, _ = cls._hunk_to_before_after(edit)
                original = "".join(original_lines)
                new_content: Optional[str] = None
                try:
                    new_content = cls.do_replace(full_path, running_content, edit)
                except SearchTextNotUnique:
                    errors.append(
                        NOT_UNIQUE_ERROR.format(
                            path=file_path,
                            original=original,
                            num_lines=len(original.splitlines()),
                        )
                    )
                    continue

                if not new_content:
                    errors.append(
                        NO_MATCH_ERROR.format(
                            path=file_path,
                            original=original,
                            num_lines=len(original.splitlines()),
                        )
                    )
                    continue

                running_content = new_content

            if running_content is not None and original_content != running_content:
                final_file_contents[file_path] = running_content

        if errors:
            errors_str = "\n\n".join(errors)
            print(errors_str)

        return FileDiffApplicationResponse(
            new_file_path=file_path,
            new_content=final_file_contents.get(file_path, ""),
        )
