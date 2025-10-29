from openai import OpenAI
import datetime


def attempt_autofix(model_path, props_path, error_output, model):
    """Attempt to fix PRISM model errors using ChatGPT."""
    client = OpenAI()
    
    # Read current model and properties
    model_code = model_path.read_text(encoding='utf-8')
    props_code = props_path.read_text(encoding='utf-8')
    
    fix_prompt = f"""You are a PRISM model checker expert. The following PRISM model has errors.

MODEL:
```
{model_code}
```

PROPERTIES:
```
{props_code}
```

ERROR OUTPUT:
```
{error_output}
```

TASK:
Fix the PRISM model to resolve the errors. Return ONLY the corrected model code, no explanations or markdown formatting."""

    resp = client.responses.create(
        model=model,
        input=[{"role": "user", "content": fix_prompt}],
    )
    
    return resp.output_text


def save_fixed_model(model_path, fixed_code):
    """Save fixed model and backup the broken original with timestamp."""
    # Backup the broken model with timestamp
    timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_path = model_path.with_suffix(f'.prism.broken-{timestamp}')
    if model_path.exists():
        backup_path.write_text(model_path.read_text(encoding='utf-8'), encoding='utf-8')
    
    # Strip markdown code blocks if present
    fixed_code = fixed_code.strip()
    if fixed_code.startswith("```"):
        lines = fixed_code.split('\n')
        fixed_code = '\n'.join(lines[1:-1]) if lines[-1].strip() == "```" else '\n'.join(lines[1:])
    
    model_path.write_text(fixed_code, encoding='utf-8')
    
    return str(backup_path)
