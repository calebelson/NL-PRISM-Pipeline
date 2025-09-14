from parser.parse_scenario import main as parse_scenario_main
from prism.generate_mdp import main as generate_mdp
from utils.meta import update_meta
import pathlib, datetime, time, datetime

def main():
    print("Run started...")
    ts = datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%SZ')
    time_zero = time.time()
    out_dir = pathlib.Path('runs') / f'prism-gen-run-{ts}'
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # ---------- NL → JSON via Structured Outputs ----------
    # user_input = """One team T1 at a with capacity 4. Resources: b=2. Demand: h=2.
    #                 Routes: a-b green distance 5, b-h yellow distance 3. Undirected.
    #                 Safety probs G 0.95, Y 0.70, R 0.30. Objective max_reach_prob
    #             """
    user_input = """
                Two teams: T1 at c, and T2 at a, each can carry 4 at a time.
                b and d have 4 resources. g wants 7 resources.
                Routes: a-b green distance 5, b-c green distance 4, c-d yellow distance 8,
                d-e red distance 6, e-f green distance 2, f-g yellow distance 3. Undirected.
                Safety probs G 0.9, Y 0.6, R 0.2. Objective max_reach_prob
                """
    scenario_obj = parse_scenario_main(user_input, out_dir)
    print("Parsed scenario and validated JSON saved.")

    # ---------- JSON → PRISM via LLM ----------
    template_text = None
    template_path = pathlib.Path('templates') / 'case-study-model.txt'
    if template_path.exists():
        template_text = template_path.read_text(encoding='utf-8')

    model = "gpt-5-mini-2025-08-07"
    print("Generating PRISM model via LLM...")
    generate_mdp(scenario_obj, template_text, out_dir, model=model)
    print("PRISM model and properties saved.")

    # ---------- Save metadata from run ----------
    elapsed = time.time() - time_zero
    elapsed_human = str(datetime.timedelta(seconds=elapsed))
    meta = {
        'time_started': ts,
        'elapsed_time': elapsed_human,
    }
    update_meta(out_dir, "overall", meta)
    print(f"Run completed. Outputs in {out_dir}")

if __name__ == "__main__":
    main()
