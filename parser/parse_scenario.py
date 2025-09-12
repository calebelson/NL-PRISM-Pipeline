# pip install openai pydantic jsonschema

from utils.meta import update_meta
from openai import OpenAI
from schema.scenario_schema import Scenario
import json, pathlib, time, datetime

# ---------- NL → JSON via Structured Outputs ----------
SYSTEM = (
    """Convert the user's disaster scenario into a JSON object that matches the provided schema.
    Do not invent nodes or edges. Use safety values only from {G,Y,R}.
    If a required value is missing, pick the smallest reasonable default and state it explicitly."""
)
MODEL = "gpt-5-2025-08-07"

def _call_llm(messages: list[dict[str, str]], model: str) -> str:
    client = OpenAI()
    resp = client.responses.parse(
        model=model,
        input=messages,
        text_format=Scenario,
    )

    return resp

def _log_response(resp, out_dir: pathlib.Path, start_time: float, messages: list[dict[str, str]]):
    out_dir.mkdir(parents=True, exist_ok=True)

    # Find first content item, which should be the JSON output
    output_item = next((item for item in resp.output if getattr(item, 'content', None)), None)
    if not (output_item and output_item.content and output_item.content[0].text):
        return None

    content = output_item.content[0].text
    raw = json.loads(content)
    validated_scenario = Scenario.model_validate(raw)
    elapsed = time.time() - start_time
    elapsed_human = str(datetime.timedelta(seconds=elapsed))

    meta = {
        "input": messages,
        "used_model": resp.model,
        "usage": str(getattr(resp, "usage", None)),
        "elapsed_time": elapsed_human,
    }

    update_meta(out_dir, "parse_scenario", meta)
    (out_dir / "validated.json").write_text(validated_scenario.model_dump_json(indent=2))

    return validated_scenario.model_dump()

def main(user_input: str, out_dir: str, model: str = MODEL):
    time_zero = time.time()
    messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_input},
        ]

    resp = _call_llm(messages, model)
    validated_json_obj = _log_response(resp, out_dir, time_zero, messages)

    # Return as dict for programmatic use
    return validated_json_obj

if __name__ == "__main__":
    main()
