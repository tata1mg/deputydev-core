import difflib
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .search_and_replace import (
    SearchTextNotUnique,
    all_preprocs,
    diff_lines,
    flexible_search_and_replace,
    search_and_replace,
)

NO_MATCH_ERROR = """UnifiedDiffNoMatch: hunk failed to apply!

{path} does not contain lines that match the diff you provided!
Try again.
DO NOT skip blank lines, comments, docstrings, etc!
The diff needs to apply cleanly to the lines in {path}!

{path} does not contain these {num_lines} exact lines in a row:
```
{original}```
"""


NOT_UNIQUE_ERROR = """UnifiedDiffNotUnique: hunk failed to apply!

{path} contains multiple sets of lines that match the diff you provided!
Try again.
Use additional ` ` lines to provide context that uniquely indicates which code needs to be changed.
The diff needs to apply to a unique set of lines in {path}!

{path} contains multiple copies of these {num_lines} lines:
```
{original}```
"""

SOME_HUNKS_APPLIED_MESSAGE = "Note: some hunks did apply successfully. See the updated source code shown above.\n\n"


class UnifiedDiffApplicator:
    def __init__(self, repo_path: str) -> None:
        self.repo_path = repo_path

    def _get_file_content(self, abs_file_path: str) -> Optional[str]:
        try:
            with open(abs_file_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                content = file_obj.read()
                return content
        except FileNotFoundError:
            return None

    def _write_file_content(self, abs_file_path: str, content: str) -> None:
        with open(abs_file_path, "w") as file_obj:
            file_obj.write(content)

    def _flexi_just_search_and_replace(self, texts: List[str]) -> Optional[str]:
        strategies = [
            (search_and_replace, all_preprocs),
        ]

        return flexible_search_and_replace(texts, strategies)

    def _directly_apply_hunk(self, content: str, hunk: List[str]) -> Optional[str]:
        before_texts, after_texts = self._hunk_to_before_after(hunk)
        before, after = "".join(before_texts).rstrip("\r\n"), "".join(after_texts).rstrip("\r\n")

        # if the before text is not in the content, we cannot apply the diff
        if not before:
            return None

        before_lines, _ = self._hunk_to_before_after(hunk)

        # get sanitized before text
        before_lines = "".join([line.strip() for line in before_lines])

        # do not do a repeated search and replace on a tiny bit of non-whitespace context
        # this is a heuristic to avoid doing a search and replace on a small amount of context
        if len(before_lines) < 10 and content.count(before) > 1:
            print("before_lines < 10 and content.count(before) > 1")
            return None

        try:
            new_content = self._flexi_just_search_and_replace([before, after, content])
        except SearchTextNotUnique:
            new_content = None

        return new_content

    def _apply_partial_hunk(
        self,
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

                res = self._directly_apply_hunk(content, this_prec + changes + this_foll)
                if res:
                    return res

    def _process_fenced_block(self, file_path_str: str, block: List[str]) -> List[Tuple[str, List[str]]]:
        """
        Cut a fenced block into hunks, hunks are basically a list of lines that have one contiguous change between them
        """
        # add a end of diff marker, will help us to cut the last diff
        print("".join(block))
        block.append("@@ @@")

        # search for the diff start marker, and if there is newline before it, we want strip it
        for i in range(len(block)):
            if block[i].startswith("--- ") and block[i + 1].startswith("+++ "):
                block = block[i + 2 :]
                break

        edits: List[Tuple[str, List[str]]] = []

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
            edits.append((file_path_str, hunk))
            hunk = []
            keeper = False

        return edits

    def find_diff_hunks(self, filepath_to_diff_map: Dict[str, str]) -> List[Tuple[str, List[str]]]:

        edits: List[Tuple[str, List[str]]] = []

        for filepath, diff in filepath_to_diff_map.items():
            if not diff.endswith("\n"):
                diff += "\n"

            # Split the diff into lines
            diff_lines = diff.splitlines(keepends=True)
            edits += self._process_fenced_block(file_path_str=filepath, block=diff_lines)

        return edits

    def _hunk_to_before_after(self, hunk: List[str]) -> Tuple[List[str], List[str]]:
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

    def _cleanup_pure_whitespace_lines(self, lines: List[str]) -> List[str]:
        """
        Remove any leading or trailing whitespace lines
        """
        res = [line if line.strip() else line[-(len(line) - len(line.rstrip("\r\n")))] for line in lines]
        return res

    def _normalize_hunk(self, hunk: List[str]) -> List[str]:
        """
        Normalize a hunk by removing any leading or trailing whitespace lines

        Args:
            hunk: A list of lines in the hunk
        """
        # get before and after lines
        before, after = self._hunk_to_before_after(hunk)

        # remove leading and trailing whitespace lines
        before = self._cleanup_pure_whitespace_lines(before)
        after = self._cleanup_pure_whitespace_lines(after)

        # get the difflib diff as LLM format can be slightly different, so we basically get a purely applicable diff
        diff = difflib.unified_diff(before, after, n=max(len(before), len(after)))

        # remove the first 2 lines as they are just the file paths
        diff = list(diff)[3:]

        endline_normalized_diff: List[str] = []
        for _line in diff:
            endline_normalized_diff.append(_line.rstrip("\r\n") + "\n")
        return endline_normalized_diff

    def _make_new_lines_explicit(self, content: str, hunk: List[str]) -> List[str]:
        before_texts, after_texts = self._hunk_to_before_after(hunk)
        before, after = "".join(before_texts), "".join(after_texts)

        diff: List[str] = diff_lines(before, content)

        back_diff: List[str] = []
        for line in diff:
            if line[0] == "+":
                continue
            # if line[0] == "-":
            #    line = "+" + line[1:]

            back_diff.append(line)

        new_before = self._directly_apply_hunk(before, back_diff)

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

    def apply_hunk(self, content: str, hunk: List[str]) -> Optional[str]:
        # before_text, after_text = self._hunk_to_before_after(hunk)

        res = self._directly_apply_hunk(content, hunk)
        if res:
            return res

        hunk = self._make_new_lines_explicit(content, hunk)

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

            res = self._apply_partial_hunk(content, preceding_context, changes, following_context)
            if res:
                content = res
            else:
                all_done = False
                # FAILED!
                # this_hunk = preceding_context + changes + following_context
                break

        if all_done:
            return content

    def do_replace(self, file_path_str: str, content: Optional[str], hunk: List[str]) -> Optional[str]:

        # get the file path as a Path object
        file_path = Path(file_path_str)
        before_texts, after_texts = self._hunk_to_before_after(hunk)
        before_text, after_text = "".join(before_texts), "".join(after_texts)

        # if the file does not exist and there is no before text, we can just create the file
        if not file_path.exists() and not before_text.strip():
            # file_path.touch()
            print("file does not exist and there is no before text")
            content = ""

        if not file_path.exists() and before_text.strip():
            print("file does not exist and there is before text")
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
        new_content = self.apply_hunk(content, hunk)
        if new_content:
            return new_content
        return None
    
    def _normalize_endlines_content(self, content: str) -> str:
        """
        Normalize the endline characters in the content
        """
        content_lines = content.splitlines(keepends=True)
        content_lines = [line.rstrip("\r\n") + "\n" for line in content_lines]
        return "".join(content_lines)

    def get_final_content(self, filepath_to_diff_map: Dict[str, str]) -> Dict[str, str]:
        """
        Get the final content of the files after applying the diffs

        Args:
            filepath_to_diff_map: A dictionary mapping file paths to unified diff strings

        Returns:
            A dictionary mapping file paths to their final content

        Raises:
            ValueError: If any of the diffs cannot be applied

        """

        final_file_contents: Dict[str, str] = {}

        # firstly, get the unique hunks
        edits = self.find_diff_hunks(filepath_to_diff_map)
        print("edits", edits)

        # remove duplicates using a set
        seen: Set[str] = set()

        # store unique non-empty normalized hunks
        unique_normalized_hunks: List[Tuple[str, List[str]]] = []
        for path, hunk in edits:
            hunk = self._normalize_hunk(hunk)
            if not hunk:
                continue

            this = [path + "\n"] + hunk
            this = "".join(this)

            if this in seen:
                continue
            seen.add(this)

            unique_normalized_hunks.append((path, hunk))

        content: Optional[str] = None
        errors: List[str] = []
        for path, hunk in unique_normalized_hunks:
            full_path = os.path.join(self.repo_path, path)
            if not content:
                content = self._get_file_content(full_path)
                content = self._normalize_endlines_content(content)

            original_lines, _ = self._hunk_to_before_after(hunk)
            original = "".join(original_lines)

            try:
                content = self.do_replace(full_path, content, hunk)
                print("content", content)
            except SearchTextNotUnique:
                errors.append(
                    NOT_UNIQUE_ERROR.format(
                        path=path,
                        original=original,
                        num_lines=len(original.splitlines()),
                    )
                )
                continue

            if not content:
                errors.append(
                    NO_MATCH_ERROR.format(
                        path=path,
                        original=original,
                        num_lines=len(original.splitlines()),
                    )
                )
                continue

            # SUCCESS!
            final_file_contents[path] = content

        if errors:
            errors_str = "\n\n".join(errors)
            if len(errors) < len(unique_normalized_hunks):
                errors_str += SOME_HUNKS_APPLIED_MESSAGE
            print(errors_str)

        return final_file_contents

    def apply_diff(self, filepath_to_diff_map: Dict[str, str]) -> None:
        """
        Apply the given diffs to the files in the repository

        Args:
            filepath_to_diff_map: A dictionary mapping file paths to unified diff strings

        Raises:
            ValueError: If any of the diffs cannot be applied

        """

        # get the final content of the files after applying the diffs
        final_file_contents = self.get_final_content(filepath_to_diff_map)

        for path, content in final_file_contents.items():
            full_path = os.path.join(self.repo_path, path)
            # SUCCESS!
            self._write_file_content(full_path, content)
