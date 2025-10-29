# NL-PRISM-Pipeline

This project uses large language models (LLMs), specifically ChatGPT, and formal verification to generate optimal resource delivery strategies for disaster response scenarios. Given a natural language description of a disaster scenario, the system automatically generates a probabilistic model, verifies it using the PRISM model checker, and produces a human-readable explanation of the optimal strategy.

## What This Does

In disaster response, teams need to deliver critical resources (medical supplies, food, equipment, etc.) through potentially hazardous environments. Each route has different safety levels, and teams must coordinate to achieve delivery objectives while maximising their chances of success.

This system takes a plain English description of such a scenario and:
1. Converts it into a structured JSON representation using OpenAI's structured outputs
2. Generates a formal PRISM model (Markov Decision Process) that captures the probabilistic nature of route safety
3. Uses PRISM to verify the model and export an optimal strategy
4. Extracts the highest-probability path through the state space using Dijkstra's algorithm
5. Generates a clear, step-by-step explanation of the strategy for human decision-makers

The goal is to bridge the gap between formal verification techniques and practical disaster response planning, making probabilistic reasoning accessible to non-technical users.

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
  - Set the `OPENAI_API_KEY` environment variable with your API key
  - Required for all LLM-based components (Parser, Composer, Navigator, Fixer)

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd dissertation

# Install Python dependencies
pip install openai

# Verify PRISM is available
which prism
prism --version
```

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

## How It Works

The pipeline consists of five main stages:

**1. Natural Language Parsing**  
User provides a scenario description (e.g., "Two teams at locations a and c, each can carry 4 resources..."). The system uses OpenAI's structured outputs to convert this into a validated JSON object containing teams, locations, resources, routes, and objectives.

**2. PRISM Model Generation**  
The JSON scenario is transformed into a PRISM model (a Markov Decision Process) where states represent team positions and resource holdings, and transitions represent team movements with probabilities based on route safety levels (red = 50%, orange = 70%, green = 90%).

**3. Verification and Strategy Export**  
PRISM verifies the model and computes the maximum probability of achieving the objective. It exports an induced strategy showing which actions maximise success probability from each reachable state. If PRISM reports errors, the system can attempt automatic fixes via LLM or regenerate the model.

**4. Optimal Path Extraction**  
The full strategy may contain thousands of states. The system re-imports the strategy to create a restricted model containing only reachable states, then uses Dijkstra's algorithm with -log(probability) weights to find the single highest-probability path from the initial state to the goal.

**5. Strategy Explanation**  
The optimal path is sent to an LLM to generate a step-by-step explanation in plain language, including transition probabilities, cumulative success rates, and final team positions. This makes the formal verification results accessible to decision-makers.

## Running the System

```bash
python main.py
```

You'll be prompted to enter a disaster scenario description. Type or paste your scenario, then press **Ctrl+D** (macOS/Linux) or **Ctrl+Z then Enter** (Windows) to submit.

Example input:
```
Two teams starting at locations a and c. Each team can carry 4 resources.
Location d has 6 resources, location g needs 8 resources.
Routes: a-b green distance 5, b-d orange distance 3, d-e red distance 4,
e-g green distance 2, c-f green distance 6, f-g orange distance 3.
```

Output files are saved to `runs/Prism_Pipeline/prism-pipeline-run-<timestamp>/`:
- `validated_scenario.json` - Parsed scenario
- `model.prism` - Generated PRISM model
- `properties.props` - PRISM property specification
- `optimal_path.txt` - Step-by-step path data
- `strategy_explanation.md` - Human-readable strategy
- `meta.json` - Complete metadata and execution logs

## Error Handling

If PRISM verification fails, the system offers three options:
- **[A] Auto-fix**: Use an LLM to attempt to fix model errors (broken models are saved as `model.prism.broken-<timestamp>`)
- **[R] Regenerate**: Generate a completely new model from scratch
- **[E] Exit**: Terminate the run

All recovery attempts are logged in `meta.json` under `prism_error_recovery` for debugging.

## Metadata and Logging

Each run produces comprehensive metadata tracking:
- Model generation settings (LLM model, template used)
- PRISM verification results (probability, strategy files, restricted model)
- Path extraction results (number of steps, success probability)
- Strategy explanation (model used, token usage)
- Error recovery attempts (if any)
- Overall execution time

This enables reproducibility and systematic analysis of the system's performance across different scenarios and configurations.

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

## Acknowledgements

This project is part of a dissertation on applying formal verification to practical decision-making problems. It builds on the PRISM model checker (www.prismmodelchecker.org) and OpenAI's language models to create a bridge between rigorous probabilistic reasoning and accessible natural language interfaces.