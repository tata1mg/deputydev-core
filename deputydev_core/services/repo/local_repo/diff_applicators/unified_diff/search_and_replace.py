from typing import Any, List, Optional, Set, Tuple
from diff_match_patch import diff_match_patch

# A custom exception for when the search text is not unique in the file
class SearchTextNotUnique(ValueError):
    pass


class RelativeIndenter:
    """Rewrites text files to have relative indentation, which involves
    reformatting the leading white space on lines.  This format makes
    it easier to search and apply edits to pairs of code blocks which
    may differ significantly in their overall level of indentation.

    It removes leading white space which is shared with the preceding
    line.

    Original:
    ```
            Foo # indented 8
                Bar # indented 4 more than the previous line
                Baz # same indent as the previous line
                Fob # same indent as the previous line
    ```

    Becomes:
    ```
            Foo # indented 8
        Bar # indented 4 more than the previous line
    Baz # same indent as the previous line
    Fob # same indent as the previous line
    ```

    If the current line is *less* indented then the previous line,
    uses a unicode character to indicate outdenting.

    Original
    ```
            Foo
                Bar
                Baz
            Fob # indented 4 less than the previous line
    ```

    Becomes:
    ```
            Foo
        Bar
    Baz
    ←←←←Fob # indented 4 less than the previous line
    ```

    This is a similar original to the last one, but every line has
    been uniformly outdented:
    ```
    Foo
        Bar
        Baz
    Fob # indented 4 less than the previous line
    ```

    It becomes this result, which is very similar to the previous
    result.  Only the white space on the first line differs.  From the
    word Foo onwards, it is identical to the previous result.
    ```
    Foo
        Bar
    Baz
    ←←←←Fob # indented 4 less than the previous line
    ```

    """

    def __init__(self, texts: List[str]):
        """
        Based on the texts, choose a unicode character that isn't in any of them.
        """

        chars: Set[str] = set()
        for text in texts:
            chars.update(text)

        ARROW = "←"
        if ARROW not in chars:
            self.marker = ARROW
        else:
            self.marker = self.select_unique_marker(chars)

    def select_unique_marker(self, chars):
        for codepoint in range(0x10FFFF, 0x10000, -1):
            marker = chr(codepoint)
            if marker not in chars:
                return marker

        raise ValueError("Could not find a unique marker")

    def make_relative(self, text):
        """
        Transform text to use relative indents.
        """

        if self.marker in text:
            raise ValueError("Text already contains the outdent marker: {self.marker}")

        lines = text.splitlines(keepends=True)

        output = []
        prev_indent = ""
        for line in lines:
            line_without_end = line.rstrip("\n\r")

            len_indent = len(line_without_end) - len(line_without_end.lstrip())
            indent = line[:len_indent]
            change = len_indent - len(prev_indent)
            if change > 0:
                cur_indent = indent[-change:]
            elif change < 0:
                cur_indent = self.marker * -change
            else:
                cur_indent = ""

            out_line = cur_indent + "\n" + line[len_indent:]
            # dump(len_indent, change, out_line)
            # print(out_line)
            output.append(out_line)
            prev_indent = indent

        res = "".join(output)
        return res

    def make_absolute(self, text):
        """
        Transform text from relative back to absolute indents.
        """
        lines = text.splitlines(keepends=True)

        output = []
        prev_indent = ""
        for i in range(0, len(lines), 2):
            dent = lines[i].rstrip("\r\n")
            non_indent = lines[i + 1]

            if dent.startswith(self.marker):
                len_outdent = len(dent)
                cur_indent = prev_indent[:-len_outdent]
            else:
                cur_indent = prev_indent + dent

            if not non_indent.rstrip("\r\n"):
                out_line = non_indent  # don't indent a blank line
            else:
                out_line = cur_indent + non_indent

            output.append(out_line)
            prev_indent = cur_indent

        res = "".join(output)
        if self.marker in res:
            # dump(res)
            raise ValueError("Error transforming text back to absolute indents")

        return res


all_preprocs = [
    # (strip_blank_lines, relative_indent, reverse_lines)
    (False, False, False),
    (True, False, False),
    (False, True, False),
    (True, True, False),
    # (False, False, True),
    # (True, False, True),
    # (False, True, True),
    # (True, True, True),
]


def diff_lines(search_text: str, replace_text: str) -> List[str]:
    dmp = diff_match_patch()
    dmp.Diff_Timeout = 5
    # dmp.Diff_EditCost = 16
    search_lines, replace_lines, mapping = dmp.diff_linesToChars(search_text, replace_text)

    diff_lines = dmp.diff_main(search_lines, replace_lines, None)
    dmp.diff_cleanupSemantic(diff_lines)
    dmp.diff_cleanupEfficiency(diff_lines)

    diff = list(diff_lines)
    dmp.diff_charsToLines(diff, mapping)
    # dump(diff)

    udiff: List[str] = []
    for d, lines in diff:
        if d < 0:
            d = "-"
        elif d > 0:
            d = "+"
        else:
            d = " "
        for line in lines.splitlines(keepends=True):
            udiff.append(d + line)

    return udiff


def search_and_replace(texts: List[str]) -> Optional[str]:
    """Search for search_text in original_text and replace it with
    replace_text. If search_text is not found, return None.
    """

    search_text, replace_text, original_text = texts

    num = original_text.count(search_text)
    # if num > 1:
    #    raise SearchTextNotUnique()
    if num == 0:
        return None

    new_text = original_text.replace(search_text, replace_text)

    return new_text


def reverse_lines(text: str) -> str:
    """
    Reverse the order of lines in a string.
    Example:
    Line 1
    Line 2
    Line 3
    becomes
    Line 3
    Line 2
    Line 1
    """
    lines = text.splitlines(keepends=True)
    lines.reverse()
    return "".join(lines)


def relative_indent(texts: List[str]) -> Tuple[RelativeIndenter, List[str]]:
    ri = RelativeIndenter(texts)
    texts = list(map(ri.make_relative, texts))

    return ri, texts


def strip_blank_lines(texts: List[str]) -> List[str]:
    # strip leading and trailing blank lines
    texts = [text.strip("\n") + "\n" for text in texts]
    return texts


def try_strategy(texts: List[str], strategy: Any, preproc: Tuple[bool, bool, bool]) -> Optional[str]:
    preproc_strip_blank_lines, preproc_relative_indent, preproc_reverse = preproc
    ri = None

    if preproc_strip_blank_lines:
        texts = strip_blank_lines(texts)
    if preproc_relative_indent:
        ri, texts = relative_indent(texts)
    if preproc_reverse:
        texts = list(map(reverse_lines, texts))

    res = strategy(texts)

    if res and preproc_reverse:
        res = reverse_lines(res)

    if res and preproc_relative_indent:
        try:
            res = ri.make_absolute(res)
        except ValueError:
            return

    return res


def flexible_search_and_replace(
    texts: List[str], strategies: List[Tuple[Any, List[Tuple[bool, bool, bool]]]]
) -> Optional[str]:
    """Try a series of search/replace methods, starting from the most
    literal interpretation of search_text. If needed, progress to more
    flexible methods, which can accommodate divergence between
    search_text and original_text and yet still achieve the desired
    edits.
    """

    for strategy, preprocs in strategies:
        for preproc in preprocs:
            res = try_strategy(texts, strategy, preproc)
            if res:
                return res
