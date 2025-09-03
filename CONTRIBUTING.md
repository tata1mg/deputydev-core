# Contributing to DeputyDev Core

Thanks for your interest in improving DeputyDev Core! This guide explains the project layout, local development workflows, code style, and how to submit changes.

If you’re new to this codebase, start with the README and in-code docstrings. Any previously separate docs pages are no longer required.


## Project layout (quick tour)

- deputydev_core/ — Python package source
  - clients/ — HTTP clients, adapters, and session managers
    - http/base_http_client.py — Common HTTP client utilities
    - http/base_http_session_manager.py — Shared aiohttp session lifecycle
    - http/adapters/ — Response adapters
    - http/service_clients/ — Service-specific clients (e.g., one_dev_client.py)
  - services/ — Core services and tools
    - repository/ — Weaviate repositories and schema services
    - tools/ — Reusable tools (grep_search, file_path_search, iterative_file_reader, focussed_snippet_search, relevant_chunks, etc.)
      - dataclass/ — Tool input/output schemas
    - file_summarization/ — File summarizer utilities
    - reranker/ — Chunk reranking strategies (heuristic/LLM)
  - models/ — DTOs and DAOs
    - dto/ — Pydantic models for inputs/outputs
    - dao/weaviate/ — Weaviate ORM-like accessors and schema details
  - utils/ — Shared utilities and constants
    - app_logger.py — Project logger helper
    - config_manager.py, mcp_settings.py — Configuration helpers
    - constants/ — Shared enums, error codes, and constants
    - exceptions.py — Common exception types
    - file_utils.py, chunk_utils.py, jwt_handler.py, etc.
  - __init__.py, py.typed — Typed package marker
- pyproject.toml — Project metadata, dependencies, Python version
- ruff.toml — Lint/format rules
- .pre-commit-config.yaml — Hooks (Ruff, uv-lock)
- uv.lock — Dependency lockfile
- README.md — Overview, prerequisites, and local setup
- CODE_OF_CONDUCT.md — Community standards
- CHANGELOG.md — Release notes (if used)

Important: This is a typed package (py.typed). Keep public APIs annotated and stable.


## Prerequisites and local setup

To avoid duplication, prerequisites (Python versions, uv) and setup steps live in README.md. Follow the README for installing dependencies, enabling pre-commit, and running local checks.


## Install and build

See README.md for the authoritative setup and build instructions (uv sync, pre-commit install, Ruff commands). This document focuses on contribution workflows and standards.


## Code style and quality

Type hints and style
- Type hints are required for function parameters and return types (public and private). Annotate *args/**kwargs as needed.
- Keep modules cohesive and small. Extract helpers to deputydev_core/utils when appropriate.
- Avoid top-level side effects on import; prefer explicit functions/classes.

Ruff (lint and format)
- Format: ruff format .
- Lint: ruff check .
- Config: ruff.toml (line-length 120, import ordering, PEP8 naming, complexity checks, no print statements, prefer pathlib, etc.)

Pre-commit
- Install: pre-commit install
- Run all hooks: pre-commit run --all-files

Logging and errors
- Use utils.app_logger for consistent logging.
- Use/customize utils.exceptions for domain-specific errors where appropriate.

Public APIs
- Only re-export in package __init__.py if meant to be public. Keep surface area stable.


## Working on core functionality

HTTP clients
- Implement service integrations under deputydev_core/clients/http/service_clients/.
- Reuse base_http_client.py and base_http_session_manager.py for consistent behavior.
- Use adapters for consistent response handling.

Services and tools
- Add new tools under deputydev_core/services/tools/<tool_name>/ with a dataclass/ subfolder for input/output schemas.
- Keep tools modular and reusable; avoid cross-cutting side effects.

Repositories and Weaviate
- Follow existing patterns in deputydev_core/services/repository/ and dao/weaviate/.
- Extend schema/service modules rather than inlining Weaviate access in business logic.

Models
- Prefer Pydantic models for DTOs (models/dto/).
- Keep DAO and schema details under models/dao/weaviate/ and services/repository/.

Constants and configuration
- Add shared constants under utils/constants/ (with clear namespacing).
- Use config_manager.py or mcp_settings.py for configuration helpers when applicable.
- If you introduce new configuration knobs, document them in README.md.


## Running checks and debugging

- ruff format .
- ruff check .
- pre-commit run --all-files

If you add a test suite (recommended for non-trivial features):
- Use pytest in a tests/ directory.
- Add minimal fixtures and keep tests fast and deterministic.


## Submitting changes

1) Fork-based workflow (default; non-maintainers)
- Non-maintainers cannot create branches on the upstream repository.
- Fork this repository to your GitHub account.
- In your fork, create a branch using the same conventions: feat/…, fix/…, chore/…, docs/…
- Push to your fork and open a Pull Request against the upstream default branch (usually main). If unsure, target main.
- Enable "Allow edits by maintainers" on the PR.

2) Maintainers-only workflow (optional)
- Maintainers may create branches directly in the upstream repository.
- Branch naming: feat/…, fix/…, chore/…, docs/…

3) Ensure quality gates pass
- Local lint/format pass (ruff format, ruff check)
- Pre-commit hooks pass
- Update README.md if you introduce user-visible changes or configuration
- Add tests or usage notes for behavioral changes

4) Commit messages
- Prefer clear, conventional-style messages (feat:, fix:, chore:, docs:, refactor:)

5) Open a Pull Request
- Describe the motivation, what changed, and how you validated it
- Link related issues
- Avoid bumping the version; maintainers handle releases


## Versioning and release notes

- Project version is defined in pyproject.toml.
- Coordinate version bumps with maintainers; do not change the version in PRs unless asked.
- If CHANGELOG.md is used, add/update entries describing user-facing changes.


## Security and privacy

- Do not commit secrets or tokens. Use local environment configuration as needed (documented in README if applicable).
- Be mindful of logs; avoid including sensitive data in logs.


## Code of Conduct

By participating, you agree to abide by our Code of Conduct. See CODE_OF_CONDUCT.md at the repository root.


## Troubleshooting

- Python version errors: Ensure your Python matches the range in pyproject.toml (>=3.11, <3.13).
- Missing tools: Ensure uv, pre-commit, and ruff are installed and available.
- Lockfile updates: If dependencies change, run uv lock (or rely on the uv-lock pre-commit hook) and commit uv.lock.
- Lint issues: Run ruff format . then ruff check . to see remaining violations.


## Questions?

Open an issue or start a discussion in the repository. Thanks again for contributing to DeputyDev Core!