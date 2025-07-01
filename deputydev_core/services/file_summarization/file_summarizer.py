import re
from typing import List, Tuple

from tree_sitter_language_pack import get_language, get_parser

from deputydev_core.models.dto.summarization_dto import FileSummaryResponse, FileType, LineRange, SummarizationStrategy
from deputydev_core.utils.app_logger import AppLogger
from deputydev_core.utils.constants.constants import (
    CODE_PATTERNS,
    DEFAULT_MAX_SUMMARY_LINES,
    IMPORTANT_NODE_TYPES,
    MAX_SIGNATURE_LINES,
)
from deputydev_core.utils.file_type_detector import FileTypeDetector


class FileSummarizer:
    def __init__(self, max_lines: int = DEFAULT_MAX_SUMMARY_LINES, include_line_numbers: bool = True) -> None:
        self.max_lines = max_lines
        self.include_line_numbers = include_line_numbers
        self.parser = None
        self.language = None

    def summarize(self, file_path: str, content: str, file_type: FileType) -> FileSummaryResponse:
        """Summarize file content based on type."""
        lines = content.splitlines()
        total_lines = len(lines)

        if file_type == FileType.CODE:
            summary_lines, ranges, skipped = self._summarize_code(lines, file_path)
            strategy = SummarizationStrategy.CODE
        elif file_type == FileType.TEXT:
            summary_lines, ranges, skipped = self._summarize_text(lines)
            strategy = SummarizationStrategy.TEXT
        else:
            summary_lines, ranges, skipped = self._sample_lines(lines)
            strategy = SummarizationStrategy.SAMPLING

        summary_content = "\n".join(
            [
                self._format_line(line, i + 1) if self.include_line_numbers else line
                for i, line in enumerate(summary_lines)
            ]
        )

        return FileSummaryResponse(
            file_path=file_path,
            file_type=file_type,
            strategy_used=strategy,
            total_lines=total_lines,
            summary_lines=len(summary_lines),
            summary_content=summary_content,
            line_ranges=ranges,
            skipped_ranges=skipped,
        )

    def _summarize_code(
        self, lines: List[str], file_path: str = ""
    ) -> Tuple[List[str], List[LineRange], List[LineRange]]:
        """Extract important code structures using tree-sitter or regex fallback."""
        content = "\n".join(lines)

        # Try tree-sitter first if available
        if self._setup_parser(file_path):
            return self._summarize_code_with_tree_sitter(content, lines)

        return self._summarize_code_with_regex(lines)

    def _setup_parser(self, file_path: str) -> bool:
        language_name = FileTypeDetector.get_language_from_file(file_path)
        if not language_name:
            return False

        try:
            self.language = get_language(language_name)
            self.parser = get_parser(language_name)
            return True
        except Exception as e:  # noqa: BLE001
            AppLogger.log_error(f"Error setting up parser for {file_path}: {str(e)}")
            return False

    def _summarize_code_with_tree_sitter(
        self, content: str, lines: List[str]
    ) -> Tuple[List[str], List[LineRange], List[LineRange]]:
        """Use tree-sitter to extract code structures."""
        try:
            tree = self.parser.parse(content.encode("utf-8"))
            important_lines = []
            ranges = []

            # Extract important nodes from AST
            self._extract_important_nodes(tree.root_node, content.encode("utf-8"), important_lines, ranges, lines)

            # Limit results
            important_lines = important_lines[: self.max_lines]
            ranges = ranges[: self.max_lines]

            # Log detailed findings
            structure_counts = {}
            multi_line_constructs = 0

            for r in ranges:
                structure_counts[r.content_type] = structure_counts.get(r.content_type, 0) + 1
                if r.end_line > r.start_line:
                    multi_line_constructs += 1

            skipped = self._calculate_skipped(lines, [r.start_line for r in ranges])
            return important_lines, ranges, skipped

        except Exception as e:  # noqa: BLE001
            AppLogger.log_error(f"Error with tree-sitter parsing: {str(e)}")

    def _extract_important_nodes(
        self, node: object, source_code: bytes, important_lines: List[str], ranges: List[LineRange], lines: List[str]
    ) -> int:
        """Recursively extract important nodes from AST."""
        nodes_found = 0

        if node.type in IMPORTANT_NODE_TYPES:
            start_line = node.start_point[0] + 1  # Convert to 1-indexed
            end_line = node.end_point[0] + 1  # Convert to 1-indexed

            # Extract construct name from the node
            construct_name = self._extract_construct_name(node, source_code)

            if start_line <= len(lines):
                # Get the declaration line(s)
                line_content = self._get_declaration_content(lines, start_line, end_line, node.type)

                # Ensure line_content isn't None or empty
                if line_content:
                    important_lines.append(line_content)
                    content_type = self._map_node_type(node.type)

                    # Create enhanced line range with construct details
                    line_range = LineRange(
                        start_line=start_line,
                        end_line=end_line,
                        content_type=content_type,
                        construct_name=construct_name,
                        description=f"{content_type.title()} spanning {end_line - start_line + 1} lines",
                    )
                    ranges.append(line_range)
                    nodes_found += 1

        # Recursively process children
        for child in node.children:
            if len(important_lines) >= self.max_lines:
                break
            nodes_found += self._extract_important_nodes(child, source_code, important_lines, ranges, lines)

        return nodes_found

    def _extract_construct_name(self, node: object, source_code: bytes) -> str:  # noqa: C901
        """Extract the name of a construct (function, class, etc.) from a tree-sitter node."""
        try:
            # Look for identifier nodes that represent the name
            for child in node.children:
                if child.type == "identifier":
                    name_bytes = source_code[child.start_byte : child.end_byte]
                    return name_bytes.decode("utf-8")
                # For some languages, the name might be nested deeper
                elif child.type in ["name", "class_name", "function_name"]:
                    name_bytes = source_code[child.start_byte : child.end_byte]
                    return name_bytes.decode("utf-8")
                # Recursive search in children
                elif child.children:
                    name = self._extract_construct_name(child, source_code)
                    if name:
                        return name
        except Exception as e:  # noqa: BLE001
            AppLogger.log_error(f"Error in finding construct name: {str(e)}")
            pass

        # Fallback: extract from source text using patterns
        try:
            node_text = source_code[node.start_byte : node.end_byte].decode("utf-8")
            first_line = node_text.split("\n")[0]

            # Pattern matching for different constructs
            if "class" in first_line:
                match = re.search(r"class\s+(\w+)", first_line)
                if match:
                    return match.group(1)
            elif "def" in first_line or "function" in first_line:
                match = re.search(r"(?:def|function)\s+(\w+)", first_line)
                if match:
                    return match.group(1)
            elif "import" in first_line:
                return first_line.strip()
        except Exception as e:  # noqa: BLE001
            AppLogger.log_error(f"Error in string matching for construct: {str(e)}")
            pass

        return "unnamed"

    def _get_declaration_content(self, lines: List[str], start_line: int, end_line: int, node_type: str) -> str:
        """Get the declaration content for a construct."""
        if start_line > len(lines):
            return ""

        # For single-line constructs (imports, decorators)
        if node_type in ["import_statement", "import_declaration", "import_from_statement", "decorator"]:
            return lines[start_line - 1]

        # For multi-line constructs, get the signature/header
        if node_type in [
            "function_definition",
            "function_declaration",
            "method_definition",
            "class_definition",
            "class_declaration",
        ]:
            signature_lines = []
            max_lines = min(MAX_SIGNATURE_LINES, end_line - start_line + 1)

            for i in range(start_line - 1, min(start_line - 1 + max_lines, len(lines))):
                line = lines[i]
                signature_lines.append(line)

                # Stop at colon (Python) or opening brace (JS/Java/C++)
                if ":" in line or "{" in line:
                    break
                # Stop at closing parenthesis for function signatures
                if line.strip().endswith(")") and "(" in "".join(signature_lines):
                    break

            return "\n".join(signature_lines)

        # Default: return the first line
        return lines[start_line - 1]

    def _map_node_type(self, node_type: str) -> str:
        # todo:  make this common logic across code
        """Map tree-sitter node types to our content types."""
        if "class" in node_type:
            return "class"
        elif "function" in node_type or "method" in node_type:
            return "function"
        elif "import" in node_type:
            return "import"
        elif "decorator" in node_type or "annotation" in node_type:
            return "decorator"
        elif node_type in ["interface_declaration", "enum_declaration", "struct_declaration"]:
            return "declaration"
        else:
            return "code_structure"

    def _summarize_code_with_regex(self, lines: List[str]) -> Tuple[List[str], List[LineRange], List[LineRange]]:
        """Fallback regex-based code structure extraction."""
        important_lines = []
        ranges = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            for pattern, content_type in CODE_PATTERNS:
                if re.match(pattern, line):
                    important_lines.append(line)
                    ranges.append(
                        LineRange(
                            start_line=i + 1,
                            end_line=i + 1,
                            content_type=content_type,
                            construct_name=self._extract_name_from_line(line, content_type),
                        )
                    )
                    break

        important_lines = important_lines[: self.max_lines]
        ranges = ranges[: self.max_lines]

        structure_counts = {}
        for r in ranges:
            structure_counts[r.content_type] = structure_counts.get(r.content_type, 0) + 1

        skipped = self._calculate_skipped(lines, [r.start_line for r in ranges])
        return important_lines, ranges, skipped

    def _extract_name_from_line(self, line: str, content_type: str) -> str:
        """Extract construct name from a line using regex."""
        try:
            if content_type == "class":
                match = re.search(r"class\s+(\w+)", line)
            elif content_type == "function":
                match = re.search(r"(?:def|function)\s+(\w+)", line)
            elif content_type == "import":
                return line.strip()
            else:
                match = re.search(r"@(\w+)", line)

            return match.group(1) if match else "unnamed"
        except Exception as e:  # noqa: BLE001
            AppLogger.log_error(f"Error in regex summarization: {str(e)}")
            return "unnamed"

    def _summarize_text(self, lines: List[str]) -> Tuple[List[str], List[LineRange], List[LineRange]]:
        """Extract headers and key text."""
        important_lines = []
        ranges = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            # Headers and list items
            if re.match(r"^#{1,6}\s+", line) or re.match(r"^\s*[-*+]\s+", line) or re.match(r"^\s*\d+\.\s+", line):
                important_lines.append(line)
                ranges.append(LineRange(start_line=i + 1, end_line=i + 1, content_type="header"))

        # Fill remaining space with paragraph samples
        if len(important_lines) < self.max_lines:
            remaining = self.max_lines - len(important_lines)
            interval = max(1, len(lines) // remaining)

            for i in range(0, len(lines), interval):
                if len(important_lines) >= self.max_lines:
                    break
                if lines[i].strip() and i + 1 not in [r.start_line for r in ranges]:
                    important_lines.append(lines[i])
                    ranges.append(LineRange(start_line=i + 1, end_line=i + 1, content_type="text"))

        skipped = self._calculate_skipped(lines, [r.start_line for r in ranges])
        return important_lines, ranges, skipped

    def _sample_lines(self, lines: List[str]) -> Tuple[List[str], List[LineRange], List[LineRange]]:
        """Simple interval sampling."""
        if len(lines) <= self.max_lines:
            summary_lines = lines
            ranges = [LineRange(start_line=i + 1, end_line=i + 1, content_type="line") for i in range(len(lines))]
            skipped = []
        else:
            interval = len(lines) // self.max_lines
            summary_lines = [lines[i] for i in range(0, len(lines), interval)][: self.max_lines]
            ranges = [
                LineRange(start_line=i * interval + 1, end_line=i * interval + 1, content_type="sampled")
                for i in range(len(summary_lines))
            ]
            skipped = self._calculate_skipped(lines, [r.start_line for r in ranges])

        return summary_lines, ranges, skipped

    def _calculate_skipped(self, lines: List[str], included_line_nums: List[int]) -> List[LineRange]:
        """Calculate skipped line ranges."""
        if not included_line_nums:
            return []

        skipped = []
        all_lines = set(range(1, len(lines) + 1))
        skipped_nums = sorted(all_lines - set(included_line_nums))

        if skipped_nums:
            start = skipped_nums[0]
            end = start

            for num in skipped_nums[1:]:
                if num == end + 1:
                    end = num
                else:
                    skipped.append(LineRange(start_line=start, end_line=end, content_type="skipped"))
                    start = end = num

            skipped.append(LineRange(start_line=start, end_line=end, content_type="skipped"))

        return skipped

    def _format_line(self, line: str, line_num: int) -> str:
        """Format line with number if enabled."""
        return f"{line_num:4d}: {line}" if self.include_line_numbers else line
