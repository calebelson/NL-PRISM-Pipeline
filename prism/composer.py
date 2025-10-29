import json, re, datetime, pathlib, time
from utils.meta import update_meta
from typing import Optional
from openai import OpenAI

# ------------------- Prompts -------------------
SYSTEM = (
    "You are an expert in translating a logistics/resource distribution scenario JSON "
    "into a runnable PRISM model for probabilistic verification. "
    "Respond with ONLY two fenced code blocks: first the PRISM model (```prism), then the properties (```properties). "
    "Annotate PRISM transitions and declarations with concise comments referencing JSON paths (e.g., // teams[0].id). "
    "Add any assumptions as leading lines starting with // ASSUMPTION:."
)

USER_TASK = (
    "Given the scenario JSON (and optional template), produce: \n"
    "1. A complete PRISM model capturing nodes, team locations, movement (respecting undirected if true), and resource/demand state.\n"
    "2. A properties file with at least one property aligned to the scenario objective.\n"
    "Rules:\n"
    "- EXACTLY TWO fenced blocks. No prose outside them.\n"
    "- First fence language tag: prism. Second: properties.\n"
    "- Use // JSON:<pointer> style or // teams[i] comments for traceability.\n"
    "- If info insufficient, make minimal safe assumptions and label them.\n"
    "- If a template is provided, use it as a reference but do not copy it verbatim.\n"
    "- Ensure syntax is valid for PRISM 4.7+.\n"
    "- Unless specified, assume all routes are bidirectional.\n"
)

FENCE_MODEL_RE = re.compile(r"```prism\s*(.*?)```", re.DOTALL | re.IGNORECASE)
FENCE_PROPS_RE = re.compile(r"```properties?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

# ------------------- Helpers -------------------
def _extract_blocks(full_text: str) -> tuple[str, str]:
    model_block = None
    props_block = None
    m = FENCE_MODEL_RE.search(full_text)
    if m:
        model_block = m.group(1).strip()
    p = FENCE_PROPS_RE.search(full_text)
    if p:
        props_block = p.group(1).strip()
    if model_block and props_block:
        return model_block, props_block
    # Fallback: if wrong format, dump everything as model
    return full_text.strip(), "// (Generator did not produce a separate properties fenced block)\n"


def _build_messages(scenario_json: str, template_text: Optional[str]) -> list[dict[str, str]]:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": USER_TASK},
        {"role": "user", "content": "Scenario JSON:"},
        {"role": "user", "content": scenario_json},
    ]
    if template_text:
        messages.append({"role": "user", "content": "Template (reference only):"})
        messages.append({"role": "user", "content": template_text})
    return messages


def compose_prism_llm(messages: list[dict[str, str]], model: str) -> dict:
    client = OpenAI()
    resp = client.responses.create(
        model=model,
        input=messages
    )
    
    return resp

def _log_response(resp, out_dir: pathlib.Path, template_used: bool, start_time: float, messages: list[dict[str, str]]):
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Find first content item
    output_item = next((item for item in resp.output if getattr(item, 'content', None)), None)
    if not (output_item and output_item.content and output_item.content[0].text):
        return None
    
    content = output_item.content[0].text
    model_block, props_block = _extract_blocks(content)
    elapsed = time.time() - start_time
    elapsed_human = str(datetime.timedelta(seconds=elapsed))
    usage_obj = getattr(resp, 'usage', None)
    usage_repr = repr(usage_obj) if usage_obj is not None else None

    # Store metadata without full PRISM model (too verbose)
    meta = {
        'template_used': template_used,
        'used_model': resp.model,
        'usage': usage_repr,
        'elapsed_time': elapsed_human,
        'model_lines': len(model_block.splitlines()),
        'properties_lines': len(props_block.splitlines())
    }

    update_meta(out_dir, "composer", meta)
    (out_dir / "model.prism").write_text(model_block)
    (out_dir / "properties.props").write_text(props_block)
    (out_dir / "composer_full_response.txt").write_text(content)

    return



def main(scenario_obj: dict, template_text: Optional[str], out_dir: pathlib.Path, model: str = "gpt-5-mini-2025-08-07"):
    time_zero = time.time()
    messages = _build_messages(json.dumps(scenario_obj, indent=2), template_text)
    resp = compose_prism_llm(messages, model)
    _log_response(resp, out_dir, bool(template_text), time_zero, messages)

    return
