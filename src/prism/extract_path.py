"""
Extract optimal path from PRISM strategy exports.

Parses PRISM's induced strategy (.tra), state space (.sta), and labels (.lab)
to reconstruct the optimal path from initial state to goal using Dijkstra's algorithm.

Note that, while it tries to find the goal state, if no goal state is labeled,
it infers one based on xg >= 7 as a fallback.
"""

import pathlib
import heapq
import math
from typing import Dict, List, Tuple, Any, Optional


def parse_labels(labels_file: pathlib.Path) -> Tuple[Dict[str, int], Dict[int, List[str]]]:
    """Parse PRISM labels file (.lab) and return label mappings."""
    lines = labels_file.read_text().strip().split('\n')
    
    # First line: 0="init" 1="deadlock" 2="goal"
    label_to_id = {}
    id_to_label = {}
    for token in lines[0].split():
        if '=' in token:
            idx, name = token.split('=', 1)
            idx = int(idx)
            name = name.strip('"')
            label_to_id[name] = idx
            id_to_label[idx] = name
    
    # Rest: state_id: label_ids
    state_to_labels = {}
    for line in lines[1:]:
        if ':' not in line:
            continue
        state_id, label_ids_str = line.split(':', 1)
        state_id = int(state_id.strip())
        label_ids = [int(x.strip()) for x in label_ids_str.strip().split()]
        state_to_labels[state_id] = [id_to_label[lid] for lid in label_ids if lid in id_to_label]
    
    return label_to_id, state_to_labels


def parse_states(states_file: pathlib.Path) -> Tuple[List[str], Dict[int, Dict[str, Any]]]:
    """Parse PRISM states file (.sta) and return variable names and state values."""
    lines = states_file.read_text().strip().split('\n')
    
    # First line: (var1,var2,var3,...)
    var_names = [v.strip() for v in lines[0].strip().strip('()').split(',')]
    
    # Rest: state_id:(val1,val2,val3,...)
    states = {}
    for line in lines[1:]:
        if ':' not in line:
            continue
        state_id_str, values_str = line.split(':', 1)
        state_id = int(state_id_str.strip())
        values = [v.strip() for v in values_str.strip().strip('()').split(',')]
        
        # Parse values as int, float, or string
        parsed_values = []
        for v in values:
            try:
                parsed_values.append(float(v) if '.' in v else int(v))
            except ValueError:
                parsed_values.append(v)
        
        states[state_id] = dict(zip(var_names, parsed_values))
    
    return var_names, states


def parse_strategy(strategy_file: pathlib.Path) -> Tuple[Dict[int, int], Dict[Tuple[int, int], List[Tuple[int, float, Optional[str]]]]]:
    """Parse PRISM strategy file (.tra) and return optimal choices and transitions."""
    lines = strategy_file.read_text().strip().split('\n')
    
    state_to_choice = {}
    transitions = {}
    
    for line in lines[1:]:  # Skip header
        parts = line.split()
        if len(parts) < 4:
            continue
        
        state = int(parts[0])
        choice = int(parts[1])
        dest = int(parts[2])
        prob = float(parts[3])
        action = parts[4] if len(parts) > 4 else None
        
        # Track optimal choice for each state
        if state not in state_to_choice:
            state_to_choice[state] = choice
        
        # Store transition
        key = (state, choice)
        if key not in transitions:
            transitions[key] = []
        transitions[key].append((dest, prob, action))
    
    return state_to_choice, transitions


def _is_failed_state(state_id: int, states: Dict[int, Dict[str, Any]]) -> bool:
    """Check if any team in this state has failed (location = -1)."""
    state_vars = states.get(state_id, {})
    for var_name, var_value in state_vars.items():
        if var_name.startswith('loc') and var_value == -1:
            return True
    return False


def _build_human_readable_output(path: List[Dict], initial_state: int, 
                                  final_state: int, path_probability: float) -> str:
    """Generate human-readable text summary of the optimal path."""
    lines = [
        "Optimal Path (Maximum Probability Path via PRISM Induced Strategy)",
        "=" * 60,
        f"Total steps: {len(path)}",
        f"Initial state: {initial_state}",
        f"Final state: {final_state}",
        f"Goal reached: YES",
        f"Path probability: {path_probability:.6f}",
        "Note: This path MAXIMIZES success probability",
        "      Failed states (team location = -1) are excluded",
        "\nPath:",
        "-" * 60
    ]
    
    for entry in path:
        lines.append(f"\nStep {entry['step']}: State {entry['state_id']}")
        lines.append(f"  Labels: {', '.join(entry['labels']) if entry['labels'] else 'none'}")
        lines.append("  Variables:")
        for var, val in entry['state'].items():
            lines.append(f"    {var} = {val}")
        
        if 'action' in entry and entry['action']:
            lines.append(f"  Action: {entry['action']} (prob={entry['transition_prob']:.4f})")
    
    return '\n'.join(lines)


def extract_optimal_path(
    strategy_file: pathlib.Path,
    states_file: pathlib.Path,
    labels_file: pathlib.Path,
    output_dir: pathlib.Path,
    max_steps: int = 100
) -> Dict[str, Any]:
    """
    Extract the optimal path from PRISM strategy exports.
    
    Uses Dijkstra's algorithm to find the highest probability path from 
    initial to goal state, excluding states where teams have failed.
    
    Returns a dictionary with path information and success status.
    """
    # Parse all files
    label_to_id, state_to_labels = parse_labels(labels_file)
    var_names, states = parse_states(states_file)
    state_to_choice, transitions = parse_strategy(strategy_file)
    
    # Find initial state
    init_states = [sid for sid, labels in state_to_labels.items() if "init" in labels]
    if not init_states:
        return {'status': 'error', 'message': 'No initial state found'}
    initial_state = init_states[0]
    
    # Find goal states
    goal_states = set(sid for sid, labels in state_to_labels.items() if "goal" in labels)
    if not goal_states:
        # Fallback: infer from xg >= 7
        print("  ⚠ No 'goal' label found, inferring from xg >= 7...")
        for state_id, state_vars in states.items():
            if 'xg' in state_vars and state_vars['xg'] >= 7:
                goal_states.add(state_id)
    
    if not goal_states:
        return {'status': 'error', 'message': 'No goal states found'}
    
    # Dijkstra's algorithm using negative log probabilities
    # -log(p1 * p2) = -log(p1) + -log(p2), so max probability = min cost
    heap = [(0.0, initial_state, [])]
    best_prob = {initial_state: 1.0}
    
    while heap:
        cost, current_state, path_so_far = heapq.heappop(heap)
        current_prob = math.exp(-cost)
        
        # Skip if we've found a better path to this state
        if current_prob < best_prob.get(current_state, 0) - 1e-10:
            continue
        
        # Skip failed states
        if _is_failed_state(current_state, states):
            continue
        
        # Build current step
        current_entry = {
            'step': len(path_so_far),
            'state_id': current_state,
            'state': states.get(current_state, {}),
            'labels': state_to_labels.get(current_state, []),
            'cumulative_prob': current_prob
        }
        path = path_so_far + [current_entry]
        
        # Check if we reached goal
        if current_state in goal_states:
            # Annotate path with actions and probabilities
            path_probability = 1.0
            for i in range(len(path) - 1):
                curr_state = path[i]['state_id']
                next_state = path[i + 1]['state_id']
                choice = state_to_choice.get(curr_state, 0)
                trans_list = transitions.get((curr_state, choice), [])
                for dest, prob, action in trans_list:
                    if dest == next_state:
                        path_probability *= prob
                        path[i]['action'] = action
                        path[i]['transition_prob'] = prob
                        break
            
            # Write human-readable output
            output_text = _build_human_readable_output(path, initial_state, current_state, path_probability)
            human_file = output_dir / 'optimal_path.txt'
            human_file.write_text(output_text)
            
            return {
                'status': 'success',
                'path': path,
                'num_steps': len(path),
                'txt_file': str(human_file),
                'goal_reached': True,
                'optimal_path_probability': path_probability,
                'initial_state': initial_state,
                'final_state': current_state
            }
        
        # Check max steps limit
        if len(path) > max_steps:
            continue
        
        # Get optimal choice for current state
        choice = state_to_choice.get(current_state)
        if choice is None:
            continue  # Dead end
        
        # Explore all successors
        trans_list = transitions.get((current_state, choice), [])
        for dest, prob, action in trans_list:
            if prob <= 0:
                continue
            
            new_prob = current_prob * prob
            new_cost = -math.log(new_prob)
            
            # Only explore if this is better
            if new_prob > best_prob.get(dest, 0) + 1e-10:
                best_prob[dest] = new_prob
                heapq.heappush(heap, (new_cost, dest, path))
    
    # No path found
    return {
        'status': 'error',
        'message': f'No path to goal found within {max_steps} steps',
        'states_explored': len(best_prob)
    }


__all__ = ['extract_optimal_path', 'parse_labels', 'parse_states', 'parse_strategy']
