# DeputyDev Core

DeputyDev Core is a Python package that provides essential functionality for the DeputyDev cloud and DeputyDev binary projects. This README provides an overview of the project structure, tech stack, and setup instructions.

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
