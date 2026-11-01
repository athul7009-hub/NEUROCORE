
# NEUROCORE

**A local-first experimental cognitive system for intelligent agent coordination, structured memory, reasoning, and controlled computer actions.**

## Overview

NEUROCORE aims to coordinate specialized AI agents, selectively share information, maintain structured memory, and safely execute approved actions on Windows 11.

## Technology Stack

- Python 3.11
- Pydantic Settings
- Ollama (Qwen3 8B)
- Pytest
- Git

## Current Implementation — v0.1 Foundations

- Modular project structure
- Centralized environment configuration
- Structured task, agent-message, and tool-action schemas
- Console and rotating file logging
- Automated tests with Pytest

## Project Structure

```text
NEUROCORE/
├── app/
│   ├── core/
│   ├── agents/
│   └── tools/
├── tests/
├── config/
├── logs/
├── .env.example
├── .gitignore
└── README.md
```

## Setup

Clone the repository and enter its directory:

```bash
git clone <repository-url>
cd NEUROCORE
```

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install pydantic-settings pytest
```

Configure your `.env` file using `.env.example`.

Run tests:

```bash
python -m pytest -v
```

## Development Status

**Phase 0 — Foundations: In progress**

Implemented components are documented above. Agent coordination, memory, Ollama integration, and controlled computer execution remain future development work.

## Safety Philosophy

- Human approval for sensitive actions.
- Dry-run before execution.
- Local-first processing where practical.
- Verification and traceability.

## License

Not yet specified.
