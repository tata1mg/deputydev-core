JAVASCRIPT_EXTENSIONS = {
    "js": "javascript",
    "jsx": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    "es": "javascript",
    "es6": "javascript",
}
EXTENSION_TO_LANGUAGE = {"py": "python", "html": "html", "kt": "kotlin", "go": "go", "json": "json"}
TSX_EXTENSIONS = {"tsx": "tsx"}
JAVA_EXTENSIONS = {"java": "java"}
TYPESCRIPT_EXTENSIONS = {
    "ts": "typescript",
    "mts": "typescript",
    "cts": "typescript",
}

ALL_EXTENSIONS = {
    **JAVASCRIPT_EXTENSIONS,
    **TYPESCRIPT_EXTENSIONS,
    **JAVA_EXTENSIONS,
    **TSX_EXTENSIONS,
    **EXTENSION_TO_LANGUAGE,
}
