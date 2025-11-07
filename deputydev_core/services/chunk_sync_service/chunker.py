# deputydev_core/services/codebase/chunker.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from tree_sitter import Node, Tree
from tree_sitter_language_pack import get_parser

from deputydev_core.services.chunk_sync_service.constant import SUPPORTED_LANGUAGES


class RawChunk(BaseModel):
    node_name: str
    node_type: str
    start_line: int
    end_line: int
    parent_name: Optional[str] = None
    parent_type: Optional[str] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class CollectedNode(BaseModel):
    name: str
    type: str
    start_line: int
    end_line: int
    parent_name: Optional[str] = None
    parent_type: Optional[str] = None


# ---- Language node maps (best-effort across popular tree-sitter grammars) ----
LANG_IMPORT_TYPES: Dict[str, set[str]] = {
    "python": {"import_statement", "import_from_statement"},
    "javascript": {"import_declaration"},
    "typescript": {"import_declaration"},
    "go": {"import_declaration"},
    "rust": {"use_declaration"},
    "java": {"import_declaration"},
    "c": set(),  # no import, but includes #include which is preprocessor (out of AST)
    "cpp": set(),  # same as C; includes/using are not standard AST nodes
    "ruby": set(),  # typically "require" at runtime; skip
    "kotlin": {"import_list", "import_header", "import_directive"},
    "swift": {"import_declaration"},
}

# Class-like constructs
LANG_CLASS_TYPES: Dict[str, set[str]] = {
    "python": {"class_definition"},
    "javascript": {"class_declaration", "class"},
    "typescript": {"class_declaration"},
    "go": set(),  # no classes
    "rust": {"impl_item", "trait_item"},  # treat impl/trait blocks as class-like parents
    "java": {"class_declaration", "interface_declaration", "enum_declaration", "record_declaration"},
    "c": set(),
    "cpp": {"class_specifier", "struct_specifier", "union_specifier"},
    "ruby": {"class", "module"},
    "kotlin": {"class_declaration", "object_declaration", "interface_declaration"},
    "swift": {"class_declaration", "struct_declaration", "enum_declaration", "protocol_declaration"},
}

# Function/method-like constructs
LANG_FUNC_TYPES: Dict[str, set[str]] = {
    "python": {"function_definition"},
    "javascript": {"function_declaration", "method_definition", "constructor"},
    "typescript": {"function_declaration", "method_definition", "method_signature", "constructor"},
    "go": {"function_declaration", "method_declaration"},
    "rust": {"function_item"},  # methods are function_item inside impl_item
    "java": {"method_declaration", "constructor_declaration"},
    "c": {"function_definition"},
    "cpp": {
        "function_definition",
        # declarations without body inside class: field_declaration with function_declarator
        "function_declarator",
        "function_declaration",
        "constructor_or_destructor_definition",
        "operator_cast",  # rare, but method-like
    },
    "ruby": {"method", "singleton_method"},
    "kotlin": {"function_declaration", "secondary_constructor"},
    "swift": {"function_declaration", "initializer_declaration"},
}

# Python-decorator wrapper
PY_WRAPPER_TYPES = {"decorated_definition"}
PY_DECORATOR_TYPES = {"decorator"}


class TreeSitterChunker:
    """
    Language-agnostic code chunk extractor built on Tree-Sitter.

    Focus: class-like + function/method-like nodes, plus import merging.
    """

    def __init__(self, language: SUPPORTED_LANGUAGES) -> None:
        self.language = language
        self.parser = get_parser(language)
        self.import_types = LANG_IMPORT_TYPES.get(language, set())
        self.func_types = LANG_FUNC_TYPES.get(language, set())
        self.class_types = LANG_CLASS_TYPES.get(language, set())

    # --------------------------- public API ---------------------------------
    async def extract_chunks(self, file_path: Path) -> List[RawChunk]:
        # Read bytes first, keep text only for line helpers to avoid decode drift
        src_bytes: bytes = file_path.read_bytes()
        lines: List[str] = src_bytes.decode("utf-8", errors="replace").splitlines()
        tree: Tree = self.parser.parse(src_bytes)
        root: Node = tree.root_node

        nodes: list[CollectedNode] = []
        self._walk_collect(root, src_bytes, nodes)
        nodes.sort(key=lambda n: n.start_line)

        merged: list[RawChunk] = []
        skip_idx: set[int] = set()
        total_nodes: int = len(nodes)
        i: int = 0

        while i < total_nodes:
            if i in skip_idx:
                i += 1
                continue

            n = nodes[i]

            # 1) Merge import-like blocks (nice-to-have)
            if n.type in self.import_types:
                block_start: int = n.start_line
                block_end: int = n.end_line
                j: int = i + 1

                while j < total_nodes and nodes[j].type in self.import_types:
                    if not self._only_blank_or_comment_between(lines, block_end, nodes[j].start_line):
                        break
                    block_end = nodes[j].end_line
                    skip_idx.add(j)
                    j += 1

                merged.append(
                    RawChunk(
                        node_name="imports_block",
                        node_type="import_block",
                        start_line=block_start,
                        end_line=block_end,
                        parent_name=None,
                        parent_type=None,
                    )
                )
                i = j
                continue

            # 2) Class / Function-like constructs (primary goal)
            if n.type in self.func_types or n.type in self.class_types:
                start_line = n.start_line
                end_line = n.end_line

                # Python: include decorators stacked above
                if self.language == "python":
                    start_line = self._expand_python_decorators_up(start_line, lines)

                merged.append(
                    RawChunk(
                        node_name=n.name,
                        node_type=n.type,
                        start_line=start_line,
                        end_line=end_line,
                        parent_name=n.parent_name,
                        parent_type=n.parent_type,
                    )
                )
                i += 1
                continue

            # 3) Ignore standalone decorators explicitly
            if self.language == "python" and n.type in PY_DECORATOR_TYPES:
                i += 1
                continue

            # 4) Fallback (rarely used now)
            merged.append(
                RawChunk(
                    node_name=n.name,
                    node_type=n.type,
                    start_line=n.start_line,
                    end_line=n.end_line,
                    parent_name=n.parent_name,
                    parent_type=n.parent_type,
                )
            )
            i += 1

        return merged

    # --------------------------- AST helpers --------------------------------
    def _walk_collect(  # noqa: C901
        self, node: Node, src: bytes, out: List[CollectedNode], stack: List[CollectedNode] | None = None
    ) -> None:
        """
        Walk the tree once, collecting nodes of interest and attaching parent info
        using a class-like stack for accurate nesting.
        """
        if stack is None:
            stack = []

        node_type = node.type
        is_class_like = node_type in self.class_types
        is_func_like = node_type in self.func_types
        is_import_like = node_type in self.import_types
        is_py_wrapper = self.language == "python" and node_type in PY_WRAPPER_TYPES
        is_py_decorator = self.language == "python" and node_type in PY_DECORATOR_TYPES

        # Build record if we care about this node type
        should_record = is_class_like or is_func_like or is_import_like or is_py_wrapper or is_py_decorator
        rec: CollectedNode | None = None

        if should_record:
            rec = CollectedNode(
                name=self._extract_name(node, src),
                type=node_type,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            )

            # attach nearest class-like parent for function-like nodes
            if is_func_like and stack:
                for parent in reversed(stack):
                    if parent.type in self.class_types:
                        rec.parent_name = parent.name
                        rec.parent_type = "class"
                        break

            out.append(rec)

        # Manage class-like parent stack
        pushed = False
        if is_class_like:
            # push *this* class as parent for children
            # make sure we push the record we just appended
            if rec is None:
                rec = CollectedNode(
                    name=self._extract_name(node, src),
                    type=node_type,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                )
            stack.append(rec)
            pushed = True

        # Special-case: Python decorated_definition acts as a wrapper; collect inner target as function/class
        if is_py_wrapper:
            for child in node.children:
                # child is often 'function_definition' or 'class_definition' with preceding 'decorator' nodes
                self._walk_collect(child, src, out, stack)
        else:
            # Normal recursion
            for child in node.children:
                # C++: treat function declarations inside classes (field_declaration with function_declarator)
                # We still visit all children; extraction happens when their node.type matches maps.
                self._walk_collect(child, src, out, stack)

        if pushed:
            stack.pop()

    def _extract_name(self, node: Node, src: bytes) -> str:  # noqa: C901
        """
        Try multiple strategies to get a human-readable name for various grammars.
        """
        # Common field-based lookup first (many grammars expose "name" or "identifier")
        if hasattr(node, "child_by_field_name"):
            for field in ("name", "identifier", "declarator", "type", "type_name"):
                c = node.child_by_field_name(field)
                if c:
                    return src[c.start_byte : c.end_byte].decode("utf-8", errors="replace")

        # Direct child scan for common identifier nodes
        for child in node.children:
            if child.type in (
                "identifier",  # C/CPP/Java/TS/JS
                "name",  # Python/Swift/Kotlin sometimes
                "type_identifier",  # Swift/Kotlin/TS
                "field_identifier",  # C/CPP fields; sometimes used for methods
                "scoped_identifier",  # C++ qualified name
            ):
                return src[child.start_byte : child.end_byte].decode("utf-8", errors="replace")

        # Rust impl/trait: try to grab the type name inside the header
        if node.type in {"impl_item", "trait_item"}:
            for child in node.children:
                if child.type in ("type_identifier", "scoped_type_identifier", "identifier"):
                    return src[child.start_byte : child.end_byte].decode("utf-8", errors="replace")

        # C++ method declarations inside class: field_declaration -> function_declarator
        if node.type in {"function_declarator"}:
            # function_declarator -> declarator: identifier
            id_node = node.child_by_field_name("declarator") if hasattr(node, "child_by_field_name") else None
            if id_node:
                return src[id_node.start_byte : id_node.end_byte].decode("utf-8", errors="replace")

        # Java constructors sometimes expose "name" as a simple identifier in constructor_declaration
        if node.type == "constructor_declaration":
            id_node = node.child_by_field_name("name") if hasattr(node, "child_by_field_name") else None
            if id_node:
                return src[id_node.start_byte : id_node.end_byte].decode("utf-8", errors="replace")

        return "unnamed"

    # --------------------------- text helpers -------------------------------
    def _is_blank_or_comment(self, s: str) -> bool:
        t = s.strip()
        if not t:
            return True
        # lightweight, language-agnostic-ish check
        return t.startswith("#") or t.startswith("//") or t.startswith("/*") or t.startswith("*") or t.startswith("--")

    def _only_blank_or_comment_between(self, lines: List[str], end_a: int, start_b: int) -> bool:
        for ln in range(end_a + 1, start_b):
            if ln - 1 < len(lines) and not self._is_blank_or_comment(lines[ln - 1]):
                return False
        return True

    # Python: expand upward to include stacked decorators for a def/class
    def _expand_python_decorators_up(self, start_line: int, lines: List[str]) -> int:
        # start_line is 1-based
        line = start_line - 1
        while line - 1 >= 0:
            prev = lines[line - 1].strip()
            if prev.startswith("@"):
                start_line -= 1
                line -= 1
            elif self._is_blank_or_comment(prev):
                line -= 1
                continue
            else:
                break
        return start_line
