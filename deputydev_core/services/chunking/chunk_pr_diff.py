import re

from deputydev_core.services.tiktoken import TikToken
from deputydev_core.utils.config_manager import ConfigManager


def chunk_pr_diff(diff_content: str, max_lines: int = 200, overlap: int = 15) -> list[str]:
    file_pattern = re.compile(r"^a/.+ b/.+$")  # Our files start with a/b
    tiktoken_client = TikToken()

    pr_diff_token_count = tiktoken_client.count(diff_content, ConfigManager.configs["EMBEDDING"]["MODEL"])
    embeeding_token_limit = ConfigManager.configs["EMBEDDING"]["TOKEN_LIMIT"]

    if pr_diff_token_count < embeeding_token_limit:
        return [diff_content]

    #  Only make diff chunks incase limit exceeds 8191 token
    lines = diff_content.split("\n")
    chunks = []
    current_chunk = []
    line_count = 0
    file_header = None  # Maintins file path of a chunk

    for line in lines:
        if file_pattern.match(line):
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            file_header = line
            current_chunk = [file_header]
            line_count = 1
        else:
            current_chunk.append(line)
            line_count += 1

            if line_count >= max_lines:
                chunks.append("\n".join(current_chunk))
                overlap_lines = current_chunk[-overlap:]
                current_chunk = [file_header] if file_header else []
                current_chunk.extend(overlap_lines)
                line_count = len(current_chunk)

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks
