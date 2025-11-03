# NL-PRISM-Pipeline

This project uses large language models (LLMs), specifically ChatGPT, and formal verification to generate optimal resource delivery strategies for disaster response scenarios. Given a natural language description of a disaster scenario, the system automatically generates a probabilistic model, verifies it using the PRISM model checker, and produces a human-readable explanation of the optimal strategy.

## Table of Contents
- [What This Does](#what-this-does)
- [Requirements](#requirements)
  - [Software Dependencies](#software-dependencies)
  - [Installation](#installation)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [Running the System](#running-the-system)
- [Error Handling](#error-handling)
- [Metadata and Logging](#metadata-and-logging)
- [LLM Prompts Location](#llm-prompts-location)
- [Acknowledgements](#acknowledgements)

## What This Does

In disaster response, teams need to deliver critical resources (medical supplies, food, equipment, etc.) through potentially hazardous environments. Each route has different safety levels, and teams must coordinate to achieve delivery objectives while maximising their chances of success.

This system takes a plain English description of such a scenario and:
1. Converts it into a structured JSON representation using OpenAI's structured outputs
2. Generates a formal PRISM model (Markov Decision Process) that captures the probabilistic nature of route safety
3. Uses PRISM to verify the model and export an optimal strategy
4. Extracts the highest-probability path through the state space using Dijkstra's algorithm
5. Generates a clear, step-by-step explanation of the strategy for human decision-makers

The goal is to bridge the gap between formal verification techniques and practical disaster response planning, making probabilistic reasoning accessible to non-technical users.

[↑ Back to top](#nl-prism-pipeline)

## Requirements

### Software Dependencies
- **Python 3.8+** with the following packages:
  - `openai` (OpenAI API client)
  - `pathlib`, `datetime`, `time`, `subprocess`, `sys`, `re` (standard library)
  
- **PRISM Model Checker** (version 4.9 or later)
  - Must be installed and available in your system PATH
  - Download from: https://www.prismmodelchecker.org/
  - The `prism` command must be executable from the terminal

- **OpenAI API Key**
  - Required for all LLM-based components (Parser, Composer, Navigator, Fixer)
  - Must be set as an environment variable in your shell: `export OPENAI_API_KEY="your-key-here"`
  - Not stored in the project files for security

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd NL-PRISM-Pipeline

# Install Python dependencies
pip install openai

# Verify PRISM is available
which prism
prism --version
```

[↑ Back to top](#nl-prism-pipeline)

## Project Structure

```
.
├── main.py                  # Entry point - orchestrates the entire pipeline
├── parser/
│   └── parse_scenario.py    # Converts natural language to JSON using LLM
├── prism/
│   ├── composer.py          # Composes PRISM model from JSON scenario
│   ├── verification.py      # Runs PRISM verification and exports strategy
│   ├── extract_path.py      # Finds optimal path using Dijkstra's algorithm
│   └── fix_model.py         # Attempts to auto-fix PRISM model errors
├── navigator/
│   └── navigator.py         # Generates human-readable strategy explanations
├── schema/
│   └── scenario_schema.py   # Pydantic schema for structured output validation
├── utils/
│   └── meta.py              # Metadata tracking and logging utilities
├── templates/
│   └── case-study-model.txt # Example PRISM model for few-shot prompting
└── runs/
    └── Prism_Pipeline/      # Output directory for each run
```

[↑ Back to top](#nl-prism-pipeline)

## How It Works

The pipeline consists of five main stages:

**1. Natural Language Input (Disaster Scenario)**  
User provides a plain English description of the disaster scenario (e.g., "Two teams at locations a and c, each can carry 4 resources..."), including team positions, resource locations, route safety levels, and delivery objectives.

**2. Parser: Natural Language → JSON**  
The Parser uses OpenAI's structured outputs to convert the natural language description into a validated JSON object containing teams, locations, resources, routes, and objectives. This structured representation is validated against a Pydantic schema to ensure completeness and correctness.

**3. Composer: JSON → PRISM Model**  
The Composer transforms the JSON scenario into a formal PRISM model (a Markov Decision Process) where states represent team positions and resource holdings, and transitions represent team movements with probabilities based on route safety levels (e.g., red = 50%, orange = 70%, green = 90%).

**4. Verification: PRISM Model Checker**  
PRISM verifies the model and computes the maximum probability of achieving the objective. It exports an induced strategy showing which actions maximise success probability from each reachable state. If PRISM reports errors, the system can attempt automatic fixes via LLM or regenerate the model.

**Note**: If no goal label is found in PRISM's output, the system defaults to inferring the goal state as `xg >= 7`. If you're adapting this pipeline for your own scenarios, you should adjust this inference logic in the path extraction code to match your specific goal conditions.

**5. Navigator: Strategy Explanation**  
The Navigator takes the verified strategy and produces a human-readable explanation:
- **Path Extraction**: The full strategy may contain hundreds of thousands of states. The system re-imports the strategy to create a restricted model containing only reachable states, then uses Dijkstra's algorithm with -log(probability) weights to find the single highest-probability path from the initial state to the goal.
- **Explanation Generation**: The optimal path is sent to an LLM to generate a step-by-step explanation in plain language, including transition probabilities, cumulative success rates, and final team positions. This makes the formal verification results accessible to decision-makers.

[↑ Back to top](#nl-prism-pipeline)

## Running the System

```bash
python main.py
```

You'll be prompted to enter a disaster scenario description. Type or paste your scenario, then press **Ctrl+D** (macOS/Linux) or **Ctrl+Z then Enter** (Windows) to submit.

**Performance Note**: With the default model (`gpt-5-mini-2025-08-07`), a typical run takes 5-10 minutes and costs approximately $0.10 in API usage (as of October 2025).

Example input:
```
Two teams: T1 at a, and T2 at c, each can carry 4 resources at a time.
Point c has 4 resources, a and d each have 2. Point g wants 7 resources.
Routes: a-b red distance 9, a-d red distance 5, b-c red distance 4, b-d yellow distance 12, c-g red distance 6, c-f red distance 12, d-e green distance 2, e-f green distance 4, f-g yellow distance 10. Undirected.
Safety probabilities are green = 0.99, yellow = 0.85, red = 0.5. Objective is to maximise probability of reaching the goal.
```

Output files are saved to `runs/Prism_Pipeline/prism-pipeline-run-<timestamp>/`:
- `validated_scenario.json` - Parsed scenario
- `model.prism` - Generated PRISM model
- `properties.props` - PRISM property specification
- `optimal_path.txt` - Step-by-step path data
- `strategy_explanation.md` - Human-readable strategy
- `meta.json` - Complete metadata and execution logs

[↑ Back to top](#nl-prism-pipeline)

## Error Handling

If PRISM verification fails, the system offers three options:
- **[A] Auto-fix**: Use an LLM to attempt to fix model errors (broken models are saved as `model.prism.broken-<timestamp>`)
- **[R] Regenerate**: Generate a completely new model from scratch
- **[E] Exit**: Terminate the run

All recovery attempts are logged in `meta.json` under `prism_error_recovery` for debugging.

[↑ Back to top](#nl-prism-pipeline)

## Metadata and Logging

Each run produces comprehensive metadata tracking:
- Model generation settings (LLM model, template used)
- PRISM verification results (probability, strategy files, restricted model)
- Path extraction results (number of steps, success probability)
- Strategy explanation (model used, token usage)
- Error recovery attempts (if any)
- Overall execution time

This enables reproducibility and systematic analysis of the system's performance across different scenarios and configurations.

[↑ Back to top](#nl-prism-pipeline)

## LLM Prompts Location

The system uses LLM prompts at four key stages. Here's where each prompt is defined:

### 1. The Parser: Natural Language → JSON Parsing
**File**: `parser/parse_scenario.py`
- **SYSTEM prompt**: Defines the assistant's role as a disaster scenario parser
- **USER_TASK prompt**: Instructions for converting natural language to JSON
- Uses OpenAI's structured outputs with the Pydantic schema from `schema/scenario_schema.py`
- Output: Validated `validated_scenario.json` file

### 2. The Composer: JSON → PRISM Model Generation
**File**: `prism/composer.py`
- **SYSTEM prompt**: Defines role as PRISM model translation expert
- **USER_TASK prompt**: Detailed rules for generating valid PRISM models and properties
- Includes reference to optional template from `templates/case-study-model.txt`
- Uses regex patterns `FENCE_MODEL_RE` and `FENCE_PROPS_RE` to extract code blocks
- Output: PRISM-ready .prism and .props files

### 3. PRISM Model Error Auto-fixing
**File**: `prism/fix_model.py`
- **SYSTEM prompt**: Defines role as PRISM model debugger
- **USER_TASK prompt**: Instructions for analyzing and fixing PRISM syntax/semantic errors
- Input: Broken model, properties file, and PRISM error output as context
- Output: Fixed PRISM model (original is backed up as `model.prism.broken-<timestamp>`)

### 4. The Navigator: Optimal Strategy Synthesis and Explanation
**File**: `navigator/navigator.py`
- **SYSTEM prompt**: Defines role as disaster response strategy explainer
- **USER_TASK prompt**: Instructions for creating human-readable step-by-step explanations
- Input: JSON scenario + optimal path data (states, actions, probabilities)
- Output: Markdown-formatted strategy explanation

[↑ Back to top](#nl-prism-pipeline)

## Acknowledgements

This project is part of a dissertation on applying formal verification to practical decision-making problems. It builds on the PRISM model checker (www.prismmodelchecker.org) and OpenAI's language models to create a bridge between rigorous probabilistic reasoning and accessible natural language interfaces.

[↑ Back to top](#nl-prism-pipeline)