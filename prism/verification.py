import subprocess
import sys
import re
import datetime
from utils.meta import update_meta
from prism.composer import main as compose
from prism.fix_model import attempt_autofix, save_fixed_model


def run_prism_verification(out_dir, scenario_obj, template_text, model, log):
    """
    PHASE 1: Run PRISM verification and export induced strategy.
    
    Returns: (strat_path, sta_path, lab_path, prism_probability)
    """
    model_path = (out_dir / "model.prism").resolve()
    props_path = (out_dir / "properties.props").resolve()
    strat_path = (out_dir / "strat.tra").resolve()
    sta_path   = (out_dir / "strat.sta").resolve()
    lab_path   = (out_dir / "strat.lab").resolve()

    # Sanity checks
    if not model_path.exists():
        print(f"Error: model.prism not found at {model_path}")
        sys.exit(1)
    if not props_path.exists():
        print(f"Error: properties.props not found at {props_path}")
        sys.exit(1)
    
    cmd = [
        "prism",
        str(model_path),
        str(props_path),
        "-prop", "1",
        "-exportstrat", f"{str(strat_path)}:type=induced,mode=restrict,reach=false",
        "-exportmodel", str(sta_path),
        "-exportmodel", str(lab_path),
    ]

    log("Running PRISM...")
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        print("\n" + "="*60)
        print("PRISM execution failed.")
        print("="*60)
        print("stdout:\n", proc.stdout)
        print("stderr:\n", proc.stderr)
        print("="*60)
        
        # Log error to metadata
        error_meta = {
            'initial_error': proc.stdout + "\n" + proc.stderr,
            'recovery_attempts': []
        }
        
        # Give user option to retry or exit
        while True:
            choice = input("\nOptions:\n  [A] Auto-fix with ChatGPT\n  [R] Regenerate from scratch\n  [E] Exit\nChoice (A/R/E): ").strip().upper()
            
            if choice == 'A':
                print("\nAttempting auto-fix with ChatGPT...")
                
                # Get the fixed model from ChatGPT
                fixed_model = attempt_autofix(
                    model_path=model_path,
                    props_path=props_path,
                    error_output=proc.stdout,
                    model=model
                )
                
                # Save the fixed model and get backup path
                backup_path = save_fixed_model(model_path, fixed_model)
                
                log("Fixed model saved, retrying PRISM...")
                
                # Log this attempt
                error_meta['recovery_attempts'].append({
                    'method': 'auto-fix',
                    'broken_model_backup': backup_path
                })
                
                # Retry PRISM execution
                print("Running PRISM:\n", " ".join(cmd))
                proc = subprocess.run(cmd, capture_output=True, text=True)
                
                if proc.returncode == 0:
                    print("✓ PRISM finished successfully after auto-fix.")
                    error_meta['resolution'] = 'auto-fix-success'
                    update_meta(out_dir, "prism_error_recovery", error_meta)
                    break
                else:
                    print("\n" + "="*60)
                    print("PRISM execution failed again after auto-fix.")
                    print("="*60)
                    print("stdout:\n", proc.stdout)
                    print("stderr:\n", proc.stderr)
                    print("="*60)
                    error_meta['recovery_attempts'][-1]['result'] = 'failed'
                    error_meta['recovery_attempts'][-1]['error'] = proc.stdout + "\n" + proc.stderr
                    # Loop back to ask again
            
            elif choice == 'R':
                print("\nRegenerating model from scratch...")
                
                # Backup the broken model before regenerating with timestamp
                timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
                backup_path = model_path.with_suffix(f'.prism.broken-{timestamp}')
                if model_path.exists():
                    backup_path.write_text(model_path.read_text(encoding='utf-8'), encoding='utf-8')
                
                log(f"Generating PRISM model via {model}...")
                compose(scenario_obj, template_text, out_dir, model=model)
                log("PRISM model and properties regenerated.")
                
                # Log this attempt
                error_meta['recovery_attempts'].append({
                    'method': 'regenerate',
                    'broken_model_backup': str(backup_path)
                })
                
                # Retry PRISM execution
                print("Running PRISM:\n", " ".join(cmd))
                proc = subprocess.run(cmd, capture_output=True, text=True)
                
                if proc.returncode == 0:
                    print("✓ PRISM finished successfully on retry.")
                    error_meta['resolution'] = 'regenerate-success'
                    update_meta(out_dir, "prism_error_recovery", error_meta)
                    break
                else:
                    print("\n" + "="*60)
                    print("PRISM execution failed again.")
                    print("="*60)
                    print("stdout:\n", proc.stdout)
                    print("stderr:\n", proc.stderr)
                    print("="*60)
                    error_meta['recovery_attempts'][-1]['result'] = 'failed'
                    error_meta['recovery_attempts'][-1]['error'] = proc.stdout + "\n" + proc.stderr
                    # Loop back to ask again
                    
            elif choice == 'E':
                print("Exiting...")
                error_meta['resolution'] = 'user-exit'
                update_meta(out_dir, "prism_error_recovery", error_meta)
                sys.exit(1)
            else:
                print("Invalid choice. Please enter A, R, or E.")
    
    # Parse verification probability from PRISM output
    prism_probability = None
    result_match = re.search(r'Result:\s+([\d.]+)', proc.stdout)
    if result_match:
        prism_probability = float(result_match.group(1))

    log(f"PRISM run. Strat, sta, and lab artifacts generated. Success probability: {prism_probability:.6f}")
    
    return strat_path, sta_path, lab_path, prism_probability


def export_restricted_model(out_dir, strat_path, sta_path, lab_path, log):
    """
    PHASE 2: Re-import induced strategy and export restricted model.
    
    Returns: (use_restricted, path_strat_file, path_sta_file, path_lab_file)
    """
    log("Re-importing strategy to build restricted model...")
    
    # Create .all file for re-import
    strat_all_path = (out_dir / "strat.all").resolve()
    strat_all_path.write_text(f"{strat_path}\n{sta_path}\n{lab_path}\n", encoding='utf-8')
    
    # Export the restricted (reachable-only) model
    restricted_tra = (out_dir / "restricted.tra").resolve()
    restricted_sta = (out_dir / "restricted.sta").resolve()
    restricted_lab = (out_dir / "restricted.lab").resolve()

    cmd_restricted = [
        "prism",
        str(strat_all_path),
        "-exportmodel", str(restricted_tra),
        "-exportmodel", str(restricted_sta),
        "-exportmodel", str(restricted_lab),
    ]
    
    log("Exporting restricted model...")
    proc_restricted = subprocess.run(cmd_restricted, capture_output=True, text=True)
    
    if proc_restricted.returncode != 0:
        print("\n" + "="*60)
        print("Warning: Failed to export restricted model. Falling back to full strategy.")
        print("="*60)
        print("stdout:\n", proc_restricted.stdout)
        print("stderr:\n", proc_restricted.stderr)
        print("="*60)
        
        # Fallback to original files
        use_restricted = False
        path_strat_file = strat_path
        path_sta_file = sta_path
        path_lab_file = lab_path
    else:
        print("✓ Restricted model exported successfully.")
        use_restricted = True
        path_strat_file = restricted_tra
        path_sta_file = restricted_sta
        path_lab_file = restricted_lab
    
    return use_restricted, path_strat_file, path_sta_file, path_lab_file


def main(out_dir, scenario_obj, template_text, model, log):
    """
    Run PRISM verification and export strategy files.
    
    PHASE 1: Verify PRISM model & export induced strategy
    PHASE 2: Re-import strategy and export restricted model
    
    Returns: (use_restricted, path_strat_file, path_sta_file, path_lab_file, prism_probability)
    """
    # PHASE 1:
    strat_path, sta_path, lab_path, prism_probability = run_prism_verification(
        out_dir, scenario_obj, template_text, model, log
    )
    
    # PHASE 2:
    use_restricted, path_strat_file, path_sta_file, path_lab_file = export_restricted_model(
        out_dir, strat_path, sta_path, lab_path, log
    )

    # Save PRISM verification metadata
    model_path = (out_dir / "model.prism").resolve()
    props_path = (out_dir / "properties.props").resolve()
    
    prism_meta = {
        'verification_probability': prism_probability,
        'verification_probability_description': 'Maximum probability of reaching the goal as computed by PRISM model checking',
        'model_file': str(model_path),
        'properties_file': str(props_path),
        'strategy_files': {
            'tra': str(strat_path),
            'sta': str(sta_path),
            'lab': str(lab_path)
        }
    }
    if use_restricted:
        restricted_tra = (out_dir / "restricted.tra").resolve()
        restricted_sta = (out_dir / "restricted.sta").resolve()
        restricted_lab = (out_dir / "restricted.lab").resolve()
        prism_meta['restricted_model_files'] = {
            'tra': str(restricted_tra),
            'sta': str(restricted_sta),
            'lab': str(restricted_lab)
        }
    update_meta(out_dir, "prism_verification", prism_meta)
    
    return path_strat_file, path_sta_file, path_lab_file
