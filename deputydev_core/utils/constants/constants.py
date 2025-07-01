from enum import Enum
from typing import Dict, List, Set

APP_VERSION = "1.0.4"
LARGE_NO_OF_CHUNKS = 60

ALL_EXTENSIONS = {
    # Python
    'py': 'python',
    # JavaScript family
    'js': 'javascript', 'jsx': 'javascript', 'mjs': 'javascript', 'cjs': 'javascript',
    # TypeScript family
    'ts': 'typescript', 'tsx': 'typescript',
    # Java
    'java': 'java',
    # C/C++
    'c': 'c', 'h': 'c',
    'cpp': 'cpp', 'cc': 'cpp', 'cxx': 'cpp', 'hpp': 'cpp',
    # Other languages
    'go': 'go',
    'rs': 'rust',
    'rb': 'ruby',
    'php': 'php',
    'swift': 'swift',
    'kt': 'kotlin',
    'scala': 'scala',
    'css': 'css',
    'html': 'html', 'htm': 'html',
    'json': 'json',
    'yaml': 'yaml', 'yml': 'yaml',
    'sh': 'bash',
    'sql': 'sql',
    'lua': 'lua',
    'dart': 'dart',
    'r': 'r',
    'toml': 'toml',
    'xml': 'xml',
    'md': 'markdown',
    'tex': 'latex',
    'elm': 'elm',
    'zig': 'zig',
}


class PropertyTypes(Enum):
    FUNCTION = "functions"
    CLASS = "classes"
    FILE = "searchable_file_path"
    FILE_NAME = "searchable_file_name"


CHUNKFILE_KEYWORD_PROPERTY_MAP = {
    "class": [PropertyTypes.CLASS.value],
    "function": [PropertyTypes.FUNCTION.value],
    "file": [PropertyTypes.FILE.value, PropertyTypes.FILE_NAME.value],
}


class ExtendedEnum(Enum):
    @classmethod
    def list(cls) -> List[str]:
        return list(map(lambda c: c.value, cls))


class LLMModelNames(ExtendedEnum):
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_4 = "gpt-4"
    GPT_4_PREVIEW = "gpt-4-1106-preview"
    GPT_4_O = "gpt-4o"
    GPT_TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"


class AuthTokenKeys(Enum):
    CLI_AUTH_TOKEN = "cli_auth_token"
    EXTENSION_AUTH_TOKEN = "extension_auth_token"


class LocalDirectories(Enum):
    LOCAL_ROOT_DIRECTORY = ".deputydev"


class LocalFiles(Enum):
    LOCAL_AUTH_TOKENS_FILE = "264325ba-cbd0-47d5-9269-ac4bd19067c2.json"
    MCP_SETTINGS_FILE = "mcp_settings.json"


class TimeFormat(Enum):
    SECONDS = "SECONDS"
    MINUTES = "MINUTES"


class SupportedPlatforms(Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MAC = "darwin"


# Constants for summarization

# Special filename mappings
SPECIAL_FILENAME_MAP: Dict[str, str] = {
    'dockerfile': 'dockerfile',
    'makefile': 'make',
    'gnumakefile': 'make',
    'cmakelists.txt': 'cmake',
}

# File type extension sets
CODE_EXTENSIONS: Set[str] = {
    '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.cpp', '.c', '.h', '.hpp',
    '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.css', '.html',
    '.htm', '.sql', '.lua', '.dart', '.r', '.elm', '.zig', '.sh', '.bash'
}

TEXT_EXTENSIONS: Set[str] = {
    '.md', '.txt', '.rst', '.tex', '.org', '.adoc', '.textile'
}

CONFIG_EXTENSIONS: Set[str] = {
    '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.env', '.xml',
    '.properties', '.conf', '.config'
}

BINARY_EXTENSIONS: Set[str] = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',
    '.exe', '.dll', '.so', '.dylib', '.bin',
    '.pyc', '.pyo', '.class', '.jar', '.war',
    '.mp3', '.mp4', '.avi', '.mov', '.wmv'
}

# Tree-sitter node types for code structures
IMPORTANT_NODE_TYPES: Set[str] = {
    'class_definition', 'class_declaration', 'class',
    'function_definition', 'function_declaration', 'function', 'method_definition',
    'import_statement', 'import_declaration', 'import_from_statement',
    'decorator', 'annotation',
    'interface_declaration', 'enum_declaration', 'struct_declaration',
    'variable_declaration', 'const_declaration', 'let_declaration'
}

# Code patterns for regex fallback
CODE_PATTERNS = [
    (r'^\s*class\s+\w+', 'class'),
    (r'^\s*def\s+\w+', 'function'),
    (r'^\s*function\s+\w+', 'function'),
    (r'^\s*(import|from)\s+', 'import'),
    (r'^\s*@\w+', 'decorator'),
    (r'^\s*(public|private|protected)\s+class\s+\w+', 'class'),
    (r'^\s*(public|private|protected)?\s*(static)?\s*\w+\s*\(', 'function'),
]

# Text patterns for markdown/text files
TEXT_PATTERNS = [
    (r'^#{1,6}\s+', 'header'),
    (r'^\s*[-*+]\s+', 'list_item'),
    (r'^\s*\d+\.\s+', 'ordered_list'),
    (r'^```', 'code_block'),
    (r'^\s*>', 'quote'),
]

# Configuration limits
DEFAULT_MAX_SUMMARY_LINES = 200
DEFAULT_SAMPLING_RATIO = 0.3
LARGE_FILE_THRESHOLD = 1000  # lines
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_SIGNATURE_LINES = 3

# Directories to ignore
IGNORED_PATHS = {'.deputydev', '__pycache__', '.git', 'node_modules', '.venv', 'venv'}