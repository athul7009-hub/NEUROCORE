# NEUROCORE

**A local-first cognitive system for multi-agent coordination, structured memory, reasoning, and controlled actions.**

## Overview

NEUROCORE is an experimental local-first cognitive system built with Python for Windows 11.

It coordinates specialized AI agents, manages multiple forms of structured memory, uses local language models for reasoning, and supports controlled tool execution with security checks and human approval.

Unlike a conventional chatbot, NEUROCORE is designed around coordinated agents, selective information sharing, memory lifecycle management, verification, persistent execution tracking, and controlled actions.

## Technology Stack

- Python 3.11
- Pydantic and Pydantic Settings
- SQLite for persistent memory and execution tracking
- Ollama for local LLM inference
- Qwen3 8B for NEUROCORE conversational reasoning (default model)
- Qwen2.5 7B as the base model for the separate experimental Hermes diagnostic agent
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
- Verification of planning results before acceptance.

### 2. Structured Memory Management

NEUROCORE implements multiple coordinated memory systems:

- **Episodic Memory:** Stores completed and failed task experiences.
- **Semantic Memory:** Stores structured knowledge.
- **Procedural Memory:** Stores reusable procedures.
- **Working Memory:** Manages task-related temporary context.
- **Prospective Memory:** Manages future intentions and reminders.
- **Meta-memory and Meta-conflict:** Support memory oversight, identity resolution, retention assessment, and memory influence tracking.

Additional memory capabilities include:

- Memory access policies and authorization.
- Selective context retrieval.
- Relevance evaluation and context construction.
- Memory lifecycle management.
- Identity resolution and retention assessment.
- Memory influence tracking and metadata.

### 3. Local AI Reasoning and Runtime

- Ollama integration for local model inference.
- Structured reasoning requests and responses.
- JSON-schema-constrained model output.
- Pydantic response validation.
- Task planning through PlanningAgent.
- Reasoning metadata, confidence, and limitations.
- Runtime integration for coordinating application services.
- Local chat service integration.
- Task-complexity-based model routing.
- Configurable thinking mode for simple, complex, and structured conversational tasks.

### 4. File Analysis and Controlled Operations

- Read-only directory scanning within configured approved roots.
- File metadata collection and SHA-256 hashing.
- Duplicate candidate detection.
- Scan safety checks, including protected paths and symbolic links.
- Cloud Files placeholder handling.
- Controlled CREATE, COPY, and RENAME operations.
- Operation planning, validation, dry-run, and approval checks.
- Quarantine and recovery-related functionality.

### 5. Tool Execution and Recovery

- Centralized tool registry and execution.
- Structured tool input and output validation.
- Explicit approval requirements for consequential operations.
- Approval auditing and persistent approval-state tracking.
- Single-use approval enforcement.
- Persistent SQLite execution ledger.
- Execution fingerprints to prevent modified requests from reusing approvals.
- Startup recovery of interrupted execution records.
- Automatic retry prohibited for interrupted actions requiring manual recovery.

Tool execution is routed through the controlled executor rather than directly invoking registered handlers from application workflows.

### 6. Verification and Reliability

- Planning results are checked through VerificationAgent.
- Authenticated agent communication.
- Communication audit records.
- Database initialization and integrity safeguards.
- Controlled error handling.
- Automated regression tests covering agents, memory, security, tool execution, and file operations.

### 7. Command-Line Interface

Start NEUROCORE with:

```powershell
python -m app
```

Available operations:

1. File Analysis
2. Create Plan
3. Scan Directory
0. Exit

Planning results require verification. Consequential tool operations require the appropriate approval before execution.

The CLI currently provides focused analysis, scanning, and planning workflows. It is not a general-purpose autonomous desktop assistant.

**Manually verified CLI workflows:**

- Application initialization and clean shutdown.
- Planning workflow.
- File Analysis using an explicitly approved test directory.
- Directory scanning using the same approved directory.
- Reparse-point paths rejected by security checks.

The File Analysis and Directory Scan workflows were tested against `C:\NEUROCORE_TEST`, containing three files.

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
│   ├── llm/
│   ├── memory/
│   │   ├── episodic/
│   │   ├── semantic/
│   │   ├── procedural/
│   │   ├── working/
│   │   ├── prospective/
│   │   └── ...
│   ├── tools/
│   ├── plugins/
│   ├── bootstrap.py
│   ├── runtime.py
│   └── __main__.py
├── tests/
├── data/
├── logs/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

*This is a simplified overview; individual modules and test files are omitted. The experimental plugin and sandbox files are not part of the verified core release.*

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

Download the default NEUROCORE model:

```powershell
ollama pull qwen3:8b
```

The experimental Hermes diagnostic model uses a separate Ollama model:

```powershell
ollama pull qwen2.5:7b
```

Its custom `neurocore-hermes` model is built from the project's Modelfile when that experimental integration is configured.

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
- Protected-path and symbolic-link safety checks.
- Human approval for consequential operations.
- Dry-run and validation before execution.
- Centralized tool execution.
- Persistent execution tracking and crash recovery.
- Authenticated inter-agent communication.
- Restricted information sharing.
- Memory access authorization.
- Verification of planning results.
- Audit records that avoid storing communication payload values.
- Isolation and least-privilege requirements for future external tools and plugins.

NEUROCORE is designed to avoid unrestricted autonomous execution. Passing a plan through verification does not itself authorize execution.

### Known Platform Limitation

Windows AppContainer integration has encountered a runtime initialization failure:

```text
0xC0000142 — STATUS_DLL_INIT_FAILED
```

The related isolation tests remain skipped. Windows AppContainer isolation is therefore **not verified**.

Plugin execution and external plugin integration remain disabled until the isolation and recovery requirements can be demonstrated reliably.

### V1.2 Plugin Security Status

The experimental plugin and sandbox implementation is preserved, but it is not authorized for execution.

Current safeguards and findings:

- Plugin lifecycle activation rejects enable requests while AppContainer isolation remains unverified.
- Explicit capability approval is separate from sandbox verification and cannot independently authorize plugin execution.
- The lifecycle test suite reports **9 passed** after the fail-closed activation change.
- Static source searches found no direct references from the inspected plugin code to `ToolRegistry` or `ToolExecutor`.
- A separate static search found no references from application code outside `app/plugins` to `PluginRegistry`, `PluginLifecycleManager`, or `PluginPermissionManager`.
- These searches did not establish the absence of every possible indirect, dynamic, or runtime integration path.
- No changes to the core `ToolRegistry`, `ToolExecutor`, or Windows process launcher were justified by the current findings.

Plugin execution must remain disabled until isolation is independently verified and the plugin-to-core boundary, least-privilege permissions, explicit approval, validated execution, and recovery safeguards are demonstrated.

Existing experimental plugin and sandbox files must be preserved during this work.

## Development Status

**Milestone: V1.1 core implementation and regression validation completed; V1.2 plugin security boundary review documented, with AppContainer isolation still unverified.**

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
- Centralized tool registry and execution.
- Persistent execution ledger and crash recovery.
- Runtime and local chat integration.
- Command-line workflows.
- Automated regression testing.

### Regression and Verification Results

Latest full regression result before the final authentication commit:

**1,568 passed, 2 skipped, 1 warning.**

The warning originates from a negative test that intentionally supplies an invalid payload to verify rejection behavior. The two skipped tests concern the currently unverified Windows AppContainer integration.

The subsequent authentication/replay verification fix was committed separately:

- **Commit:** `080012d`
- **Message:** `Fix agent authentication replay verification`
- **Files changed:** 3
- **Changes:** 119 insertions, 40 deletions.

The authentication/replay fix passed its focused test group:

**112 passed, 1 warning.**

The CLI startup, planning, File Analysis, and directory scanning workflows were also manually verified.

The full regression suite has not yet been rerun after the final authentication commit.

The V1.2 plugin lifecycle validation is separate from the historical full-suite result.

## Future Development

The following capabilities are deferred beyond the current core release:

- Graphical user interface.
- Voice-controlled desktop assistant.
- Advanced hybrid local/cloud model routing.
- Direct Obsidian integration.
- Expanded external plugin ecosystem.
- Advanced autonomous workflows.

These features will be considered separately after the core system's release and stability requirements are satisfied.

## License

Not yet specified.