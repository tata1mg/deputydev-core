# DeputyDev Core

DeputyDev Core is a Python package that provides essential functionality for the DeputyDev cloud and DeputyDev binary projects. This README provides an overview of the project structure, tech stack, and setup instructions.

## Prerequisites

- Python >= 3.11, < 3.13
- uv (recommended): https://docs.astral.sh/uv/
- Git

## Local setup (uv)

1) Create and activate a virtual environment
   - uv venv
   - source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
2) Install dependencies (including dev tools)
   - uv sync --group dev
3) Install git hooks
   - pre-commit install
4) Run formatters/linters locally
   - ruff format .
   - ruff check .

Alternative (pip) setup:
- python -m venv .venv && source .venv/bin/activate
- pip install -e .
- pip install "pre-commit>=4.2.0" "ruff==0.12.0"
- pre-commit install

## Tech Stack

- **Python**: The main programming language used for the project.
- **Weaviate**: Vector database used for chunk storage and retrieval.
- **HTTP Clients**: Custom implementations for making API calls.
- **JWT**: Used for authentication purposes.
- **Embedding Services**: Likely used for text embeddings.
- **Chunking Strategies**: Used for text processing and splitting.
- **Diff Algorithms**: Used for processing code diffs.

## Project Structure

The main package is `deputydev_core`, which contains the following subpackages:

- `clients`: HTTP clients and adapters for making API calls.
- `models`: Data Transfer Objects (DTOs) and Data Access Objects (DAOs).
- `services`: Various services including embedding, chunking, diff processing, and more.
- `utils`: Utility functions, constants, and helper classes.

Key directories and their purposes:

- `deputydev_core/clients`: Contains HTTP client implementations and adapters.
- `deputydev_core/models`: Defines DTO and DAO classes for data handling.
- `deputydev_core/services`: Implements core services like embedding, chunking, and diff processing.
- `deputydev_core/utils`: Provides utility functions, constants, and shared resources.

## Contributing

For contribution guidelines, coding standards, and the PR workflow, see CONTRIBUTING.md.
