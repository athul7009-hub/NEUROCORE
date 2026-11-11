# NEUROCORE

**A local-first cognitive system for multi-agent coordination, structured memory, reasoning, and controlled actions.**

## Overview

NEUROCORE is an experimental local-first cognitive system built with Python for Windows 11.

It coordinates specialized AI agents, manages multiple forms of structured memory, uses local language models for reasoning, and supports controlled file operations with security checks and human approval.

Unlike a conventional chatbot, NEUROCORE is designed around coordinated agents, selective information sharing, memory lifecycle management, verification, and controlled execution.

## Technology Stack

- Python 3.11
- Pydantic and Pydantic Settings
- SQLite for persistent memory
- Ollama for local LLM inference
- Qwen3 8B (default reasoning model)
- Pytest for automated testing
- Git for version control

## Implemented Features

### 1. Multi-Agent Coordination

- Central Coordinator for task routing and orchestration.
- Specialized File Analysis, Planning, and Verification agents.
- Structured agent messages and task schemas.
- Controlled information sharing between agents.
- Agent authentication using HMAC signatures.
- Replay protection and communication auditing.

### 2. Structured Memory Management

NEUROCORE implements five primary memory types:

- **Episodic Memory:** Stores completed and failed task experiences.
- **Semantic Memory:** Stores structured knowledge.
- **Procedural Memory:** Stores reusable procedures.
- **Working Memory:** Manages task-related temporary context.
- **Prospective Memory:** Manages future intentions and reminders.

Additional memory capabilities include:

- Memory access policies and authorization.
- Selective context retrieval.
- Relevance evaluation and context construction.
- Memory lifecycle management.
- Identity resolution and retention assessment.
- Memory influence tracking and metadata.

### 3. Local AI Reasoning

- Ollama integration for local model inference.
- Structured reasoning requests and responses.
- JSON-schema-constrained model output.
- Pydantic response validation.
- Task planning through PlanningAgent.
- Reasoning metadata, confidence, and limitations.

### 4. File Analysis and Controlled Operations

- Read-only directory scanning within configured approved roots.
- File metadata collection and SHA-256 hashing.
- Duplicate candidate detection.
- Scan safety checks, including protected paths and symbolic links.
- Controlled CREATE, COPY, and RENAME operations.
- Operation planning, validation, dry-run, and approval checks.
- Quarantine and recovery-related functionality.

### 5. Verification and Reliability

- Planning results are checked through VerificationAgent.
- Authenticated agent communication.
- Communication audit records.
- Database integrity checks during initialization.
- Controlled error handling.
- Automated tests covering agents, memory, security, and file operations.

### 6. Command-Line Interface

Start NEUROCORE with:

```powershell
python -m app
```

Available operations:

1. File Analysis
2. Create Plan
0. Exit

Planning results require approval before execution. The CLI currently provides analysis and planning workflows; it is not a general-purpose autonomous desktop assistant.

## Project Structure

```text
NEUROCORE/
├── app/
│   ├── agents/
│   │   ├── coordinator.py
│   │   ├── file_analysis_agent.py
│   │   ├── planning_agent.py
│   │   ├── verification_agent.py
│   │   └── registry.py
│   ├── core/
│   │   ├── config.py
│   │   ├── schemas.py
│   │   ├── agent_auth.py
│   │   ├── communication_policy.py
│   │   └── communication_audit.py
│   ├── llm/
│   │   ├── ollama_client.py
│   │   ├── reasoning.py
│   │   └── schemas.py
│   ├── memory/
│   │   ├── episodic/
│   │   ├── semantic/
│   │   ├── procedural/
│   │   ├── working/
│   │   ├── prospective/
│   │   └── ...
│   ├── tools/
│   ├── bootstrap.py
│   └── __main__.py
├── tests/
├── data/
├── logs/
├── .env.example
├── .gitignore
└── README.md
```

*This is a simplified overview; individual modules and test files are omitted.*

## Setup

### 1. Prerequisites

- Windows 11
- Python 3.11
- Git
- Ollama

Install Ollama from:

https://ollama.com/

### 2. Clone the repository

```powershell
git clone <repository-url>
cd NEUROCORE
```

### 3. Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

Install the pinned project dependencies:

```powershell
python -m pip install -r requirements.txt
```

### 5. Configure Ollama

Download the default model:

```powershell
ollama pull qwen3:8b
```

Ensure Ollama is running and accessible at:

```text
http://localhost:11434
```

### 6. Configure environment variables

Create a `.env` file using `.env.example` as a reference.

Configure the agent authentication keys and approved scan directories.

Example:

```dotenv
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
LOG_LEVEL=INFO

FILE_ANALYSIS_AGENT_KEY=replace_with_a_secret
COORDINATOR_AGENT_KEY=replace_with_a_secret
PLANNING_AGENT_KEY=replace_with_a_secret
VERIFICATION_AGENT_KEY=replace_with_a_secret

ALLOWED_SCAN_ROOTS=["C:/NEUROCORE_TEST"]
```

Use strong, unique secrets for agent authentication. Keep `.env` private and never commit it.

Only configure directories that you explicitly authorize NEUROCORE to scan.

### 7. Run the application

```powershell
python -m app
```

### 8. Run the automated tests

```powershell
python -m pytest -v
```

## Security Principles

NEUROCORE follows a controlled-execution approach:

- Explicitly approved scan roots.
- Protected-path and symlink safety checks.
- Human approval for controlled operations.
- Dry-run and validation before execution.
- Authenticated inter-agent communication.
- Restricted information sharing.
- Memory access authorization.
- Verification of planning results.
- Audit records that avoid storing communication payload values.

NEUROCORE is designed to avoid unrestricted autonomous execution. Passing a plan through verification does not itself authorize execution.

## Development Status

**Milestone: Core implementation and system validation completed; V1 release preparation in progress.**

Implemented areas:

- Foundation and configuration.
- Read-only file observation.
- Controlled file operations.
- Multi-agent coordination.
- Local LLM reasoning and planning.
- Verification workflows.
- Structured memory systems.
- Memory lifecycle and context management.
- Authentication and communication security.
- Command-line workflows.
- Automated regression testing.

Latest full regression result:

**1,318 passed, 0 failed, 1 warning.**

The warning originates from a negative test that intentionally supplies an invalid payload to verify rejection behavior.

## Future Development

The following are outside the current V1 scope:

- Graphical user interface.
- Voice-controlled desktop assistant.
- Advanced hybrid local/cloud model routing.
- Direct Obsidian integration.
- Expanded autonomous workflows.

These features will be considered separately after the core system's V1 release.

## License

Not yet specified.
