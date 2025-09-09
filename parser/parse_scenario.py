# pip install openai pydantic jsonschema
# usage:
#   echo "NL description here..." | python parse_scenario_pydantic.py
#   python parse_scenario_pydantic.py input.txt

from __future__ import annotations
import sys, json, pathlib, datetime
from openai import OpenAI
from schema.scenario_schema import Scenario


# ---------- NL → JSON via Structured Outputs ----------

SYSTEM = (
    """Convert the user's disaster scenario into a JSON object that matches the provided schema.
    Do not invent nodes or edges. Use safety values only from {G,Y,R}.
    If a required value is missing, pick the smallest reasonable default and state it explicitly."""
)

def read_input() -> str:
    if not sys.stdin.isatty():
        return sys.stdin.read()
    if len(sys.argv) > 1:
        return pathlib.Path(sys.argv[1]).read_text()
    print("Usage: echo 'NL scenario...' | python parse_scenario_pydantic.py OR python parse_scenario_pydantic.py input.txt", file=sys.stderr)
    sys.exit(2)

def main(user_input: str):
    natural_language = user_input
    time_stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    base = pathlib.Path("runs") / f"parse-pydantic-{time_stamp}"
    base.mkdir(parents=True, exist_ok=True)

    client = OpenAI()

    # Build a JSON Schema from the Pydantic model
    schema = Scenario.model_json_schema()

    resp = client.responses.parse(
        model="gpt-5-2025-08-07",  # pin your prod snapshot
        input=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": natural_language},
        ],
        text_format=Scenario,
    )

    # Find the first output item with non-None content
    output_item = next((item for item in resp.output if getattr(item, 'content', None)), None)
    # Log the raw output for debugging and manual validation
    if output_item and output_item.content and output_item.content[0].text:
        # Get and validate JSON
        content = output_item.content[0].text
        raw = json.loads(content)
        validated_scenario = Scenario.model_validate(raw)

        log = {
            "input": natural_language,
            "model": resp.model,
            "usage": str(getattr(resp, "usage", None)),
            "validated_json": validated_scenario.model_dump(),
        }
        (base / "parse.log.json").write_text(json.dumps(log, indent=2))

        # Emit the validated JSON to stdout for piping into your renderer
        print(validated_scenario.model_dump_json(indent=2))
    else:
        print("Error: Could not find valid output content in response.", file=sys.stderr)
        sys.exit(1)    

if __name__ == "__main__":
    main(user_input="")