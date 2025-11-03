from utils.meta import update_meta
from openai import OpenAI


client = OpenAI()

def main(out_dir: str, model: str = "gpt-5-mini-2025-08-07"):
    # Read the TXT file for human-readable path data
    txt_path = out_dir / 'optimal_path.txt'
    txt_content = txt_path.read_text(encoding='utf-8') if txt_path.exists() else ""

    # Read original scenario for context
    scenario_path = out_dir / 'validated_scenario.json'
    scenario_content = scenario_path.read_text(encoding='utf-8') if scenario_path.exists() else "{}"

    explanation_prompt = f"""You are a disaster response expert analyzing an optimal resource delivery strategy.

    INPUT DATA:
    1. Original Scenario (JSON):
    {scenario_content[:10000]}

    2. Optimal Path (structured format):
    {txt_content}

    TASK:
    Write a step-by-step strategy summary with running success probabilities.

    STRUCTURE YOUR RESPONSE AS:
    1. **Overview** (2-3 sentences): Total steps, final success probability, and key challenge

    2. **Step-by-Step Actions** (numbered list): For EVERY step with an action:
    - Number steps sequentially starting from 1
    - Team action (e.g., "Team 1: c→d carrying 4 resources")
    - Transition probability (e.g., "60% success")
    - Running cumulative probability (e.g., "Overall: 0.54%")

    3. **Final State**: List where each team ends and where all resources are located

    GUIDELINES:
    - Only include rows with actual actions in the Action column (skip the final goal state row)
    - Number steps 1, 2, 3, ... instead of 0, 1, 2, ...
    - Show ALL transition probabilities and running cumulative probability
    - Use location names (a, b, c, etc.) not state IDs
    - Format: "Step X: Team Y: loc1→loc2 carrying N resources (P% success) | Overall: X%"
    - End with clear summary of final locations of every team and all resources.

    OUTPUT FORMAT:
    Plain markdown with ## headings, numbered list for steps. No JSON, no code blocks."""

    resp = client.responses.create(
        model=model,
        input=[{"role": "user", "content": explanation_prompt}],
    )

    strategy_explanation = resp.output_text

    # Save explanation
    explanation_file = out_dir / 'strategy_explanation.md'
    explanation_file.write_text(strategy_explanation, encoding='utf-8')
            
    # Save full explanation to metadata
    explanation_meta = {
        "file": str(explanation_file),
        "model": "gpt-5-mini-2025-08-07",
        "explanation": strategy_explanation,
        "usage": str(getattr(resp, "usage", None)),
    }
    update_meta(out_dir, "strategy_explanation", explanation_meta)
    
    return
