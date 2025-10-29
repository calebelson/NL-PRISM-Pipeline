from parser.parse_scenario import main as parse_scenario_main
from prism.composer import main as compose
from navigator.navigator import main as navigator
from utils.meta import update_meta
import pathlib, datetime, time, subprocess, sys, re

def main():
    def log(message):
        """Print message with timestamp prefix"""
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"{timestamp}: {message}")
    
    log("Run started...")
    ts = datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%SZ')
    time_zero = time.time()
    out_dir = pathlib.Path('runs/Prism_Pipeline') / f'prism-pipeline-run-{ts}'
    out_dir.mkdir(parents=True, exist_ok=True)
    model = "gpt-5-mini-2025-08-07"

    
    # ---------- NL → JSON via Structured Outputs ----------
    print("\nPlease describe your disaster response scenario")
    print("Include: teams, locations, resources, routes (with safety colors), and objective")
    print("Example: 'Two teams at a and c, each can carry 4. Point d has 6 resources, g needs 8. Routes: a-b green distance 5...'")
    print("\nEnter your scenario (press Ctrl+D on macOS/Linux or Ctrl+Z then Enter on Windows when finished):")
    print("-" * 60)
    
    try:
        lines = []
        while True:
            try:
                line = input()
                lines.append(line)
            except EOFError:
                break
        user_input = "\n".join(lines).strip()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Exiting.")
        sys.exit(1)
    
    print("-" * 60)
    if not user_input:
        print("Error: No scenario provided. Exiting.")
        sys.exit(1)
    
    log(f"Parsing scenario via {model}...")
    scenario_obj = parse_scenario_main(user_input, out_dir, model)
    log("Parsed scenario. Validated JSON saved.")

    # ---------- JSON → PRISM via LLM ----------
    template_text = None
    template_path = pathlib.Path('templates') / 'case-study-model.txt'
    if template_path.exists():
        template_text = template_path.read_text(encoding='utf-8')

    model = "gpt-5-mini-2025-08-07"
    log(f"Generating PRISM model via {model}...")
    compose(scenario_obj, template_text, out_dir, model=model)
    log("PRISM model and properties saved.")

    # ---------- PHASE 1 & 2: Verify model and export strategy ----------
    from prism.verification import main as verify_and_export_strategy
    
    path_strat_file, path_sta_file, path_lab_file = verify_and_export_strategy(
        out_dir, scenario_obj, template_text, model, log
    )

    # ---------- Extract optimal path from strategy (using restricted model if available) ----------
    log("Extracting optimal path...")
    
    from prism.extract_path import extract_optimal_path

    # Use restricted model and Djikstra's algorithm to find optimal path
    path_result = extract_optimal_path(
        strategy_file=path_strat_file,
        states_file=path_sta_file,
        labels_file=path_lab_file,
        output_dir=out_dir,
    )
    
    if path_result['status'] == 'success':
        print(f"✓ Optimal path found: {len(path_result['path'])} steps, probability={path_result.get('optimal_path_probability', 0):.6f}")
        
        # Save path metadata
        path_meta = {
            'num_steps': len(path_result['path']),
            'optimal_path_probability': path_result.get('optimal_path_probability', 0),
            'optimal_path_probability_description': 'Probability of success for this specific optimal path from the initial state',
            'initial_state': path_result.get('initial_state'),
            'final_state': path_result.get('final_state'),
            'files': {
                'txt': str(path_result.get('txt_file', ''))
            }
        }
        update_meta(out_dir, "optimal_path", path_meta)
        
        # ---------- Generate human-readable strategy explanation via LLM ----------
        model = "gpt-5-mini-2025-08-07"
        log(f"Generating strategy explanation via {model}...")
        navigator(out_dir, model)
        
    else:
        print(f"✗ Path extraction failed: {path_result.get('message', 'Unknown error')}")
    
    elapsed = time.time() - time_zero
    log(f"Run completed in {elapsed:.2f}s")



    # ---------- Save metadata from run ----------
    elapsed = time.time() - time_zero
    elapsed_human = str(datetime.timedelta(seconds=elapsed))
    meta = {
        'time_started': ts,
        'elapsed_time': elapsed_human,
    }
    update_meta(out_dir, "overall", meta)
    log(f"Run completed. Outputs in {out_dir}")


if __name__ == "__main__":
    main()
