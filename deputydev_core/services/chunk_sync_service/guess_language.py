from pathlib import Path

EXT_TO_LANG = {
    # Common languages
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".rs": "rust",
    ".swift": "swift",
    ".kt": "kotlin",
    ".m": "objective-c",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".md": "markdown",
    ".rst": "restructuredtext",
    # Compound or special files
    ".spec.ts": "typescript",
    ".test.js": "javascript",
    ".tar.gz": "archive",
    ".tgz": "archive",
}

SPECIAL_FILES = {
    "Dockerfile": "docker",
    "Makefile": "makefile",
    ".bashrc": "bash",
    ".zshrc": "bash",
    ".gitignore": "gitignore",
    "CMakeLists.txt": "cmake",
    "requirements.txt": "python-requirements",
    "package.json": "npm-config",
    "Pipfile": "python-pipenv",
}


def guess_language(abs_path: Path) -> str:
    p = abs_path
    name = p.name

    # Special filenames
    if name in SPECIAL_FILES:
        return SPECIAL_FILES[name]

    # Handle compound extensions
    suffixes = "".join(p.suffixes).lower()
    if suffixes in EXT_TO_LANG:
        return EXT_TO_LANG[suffixes]

    # Fallback to single suffix
    if p.suffix.lower() in EXT_TO_LANG:
        return EXT_TO_LANG[p.suffix.lower()]

    return "unknown"
