#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GRPO Reward Functions for TSC-CYCLE

Three-layer reward structure:
- L1: Format matching (exact + approximate)
- L2: Constraint checking (phase order + green time range)
- L3: SUMO simulation (only when L1+L2 fully pass)
- Additional: Think length penalty

All functions follow trl GRPOTrainer interface:
    def reward_func(completions, **kwargs) -> list[float]
    def reward_func(prompts, completions, **kwargs) -> list[float]
"""

import json
import os
import random
import re
from concurrent.futures import ProcessPoolExecutor
from typing import List, Dict, Any


# ============================================================================
# Module-level state
# ============================================================================

_config = None
_baseline = None
_sumo_pool = None
_print_counter = 0

# Regex for format matching
# Note: add_generation_prompt=True prepends <start_working_out>, so model generates content AFTER <start_working_out>
# Actual completion format: "思考内容<end_working_out><SOLUTION>...</SOLUTION>"
# Match pattern: require <end_working_out> followed by <SOLUTION>...</SOLUTION> at the end
match_format = re.compile(
    r"<end_working_out>.*?<SOLUTION>(.+?)</SOLUTION>\s*$",
    flags=re.DOTALL
)


def init_rewards(config_path: str, baseline_path: str):
    """Initialize reward functions with config and baseline data.

    Must be called once before training starts.

    Args:
        config_path: Path to config.json
        baseline_path: Path to baseline.json (precomputed baseline metrics)
    """
    global _config, _baseline

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        _config = config["training"]["grpo"]["reward"]

    with open(baseline_path, 'r', encoding='utf-8') as f:
        _baseline = json.load(f)

    print(f"[Rewards] Initialized with {len(_baseline)} baseline entries")


# ============================================================================
# L1: Format Matching
# ============================================================================

def match_format_exactly(completions, **kwargs) -> List[float]:
    r"""L1.1 - Exact format matching.

    Checks if response matches the exact pattern:
        <end_working_out>\s*<SOLUTION>content</SOLUTION>\s*$

    Score:
        - Full match: config.format_exact_score (default 3.0)
        - No match: 0
    """
    scores = []
    for completion in completions:
        response = completion[0]["content"]
        score = _config["format_exact_score"] if match_format.search(response) else 0.0
        scores.append(score)
    return scores


def match_format_approximately(completions, **kwargs) -> List[float]:
    """L1.2 - Approximate format matching.

    Counts tag occurrences and gives gradual scores:
        - <end_working_out> appears exactly 1 time: +0.5, else -1.0
        - <SOLUTION> appears exactly 1 time: +0.5, else -1.0
        - </SOLUTION> appears exactly 1 time: +0.5, else -1.0

    Note: <start_working_out> is prepended by add_generation_prompt, no need to check.
    """
    tag_present = _config["format_approx_scores"]["tag_present"]
    tag_absent = _config["format_approx_scores"]["tag_absent"]

    scores = []
    for completion in completions:
        response = completion[0]["content"]
        score = 0.0

        # Count each tag
        score += tag_present if response.count("<end_working_out>") == 1 else tag_absent
        score += tag_present if response.count("<SOLUTION>") == 1 else tag_absent
        score += tag_present if response.count("</SOLUTION>") == 1 else tag_absent

        scores.append(score)
    return scores


# ============================================================================
# L2: Constraint Checking
# ============================================================================

def check_constraints(prompts, completions, **kwargs) -> List[float]:
    """L2 - Gradual constraint checking.

    Extracts CyclePlan JSON and validates:
        a) Phase order correctness (compared to expected phase_ids from prompt)
        b) Green time range (min_green <= final <= max_green)

    Score components:
        - phase_order_score = (correct positions / total phases) * phase_order_weight
        - green_range_score = (satisfying phases / total phases) * green_range_weight

    Returns -2.0 if cannot extract valid JSON.
    """
    phase_order_weight = _config["constraint_phase_order_weight"]
    green_range_weight = _config["constraint_green_range_weight"]

    scores = []

    for i, (prompt, completion) in enumerate(zip(prompts, completions)):
        response = completion[0]["content"]

        # Extract CyclePlan JSON
        match = match_format.search(response)
        if not match:
            scores.append(-2.0)
            continue

        try:
            plan = json.loads(match.group(1))
        except:
            scores.append(-2.0)
            continue

        # Parse prompt to extract expected phase_ids and constraints
        # Prompt format (from GRPO data): includes phase_waits list with phase_id, min_green, max_green
        # We need to extract from prompt content
        try:
            # Assume prompt is list of messages, last is user message
            prompt_content = prompt[-1]["content"]

            # Extract phase_waits from prompt (it's embedded as JSON-like structure)
            # Example: "phase_waits": [{"phase_id": 0, "min_green": 10, "max_green": 60, ...}, ...]
            # Simple regex extraction
            import re as re_local
            phase_waits_match = re_local.search(r'"phase_waits"\s*:\s*(\[.*?\])', prompt_content, re_local.DOTALL)
            if not phase_waits_match:
                scores.append(-2.0)
                continue

            phase_waits = json.loads(phase_waits_match.group(1))
            expected_phase_ids = [p["phase_id"] for p in phase_waits]

        except:
            scores.append(-2.0)
            continue

        # Check if plan is list
        if not isinstance(plan, list):
            scores.append(-2.0)
            continue

        total_phases = len(expected_phase_ids)
        if total_phases == 0:
            scores.append(0.0)
            continue

        # a) Phase order correctness
        output_phase_ids = [p.get("phase_id") for p in plan if isinstance(p, dict)]

        if len(output_phase_ids) != total_phases:
            phase_order_score = 0.0
        else:
            correct_positions = sum(1 for exp, out in zip(expected_phase_ids, output_phase_ids) if exp == out)
            phase_order_score = (correct_positions / total_phases) * phase_order_weight

        # b) Green time range
        satisfying_count = 0
        for j, phase in enumerate(plan):
            if not isinstance(phase, dict):
                continue

            phase_id = phase.get("phase_id")
            final = phase.get("final")

            # Find corresponding constraint
            constraint = next((p for p in phase_waits if p["phase_id"] == phase_id), None)
            if not constraint:
                continue

            min_green = constraint["min_green"]
            max_green = constraint["max_green"]

            # Check if final is integer and in range
            if isinstance(final, int) and min_green <= final <= max_green:
                satisfying_count += 1

        if len(plan) == 0:
            green_range_score = 0.0
        else:
            green_range_score = (satisfying_count / len(plan)) * green_range_weight

        # Total score
        total_score = phase_order_score + green_range_score
        scores.append(total_score)

    return scores


# ============================================================================
# L3: SUMO Simulation Reward
# ============================================================================

def get_sumocfg_for_state(state_file_relative: str) -> str:
    """Map state file path to its sumocfg.

    Rules:
        - arterial4x4_* -> sumo_simulation/arterial4x4/arterial4x4_*/arterial4x4.sumocfg
        - chengdu -> sumo_simulation/environments/chengdu/chengdu.sumocfg
    """
    parts = state_file_relative.split('/')
    scenario = parts[2]  # e.g. "arterial4x4_10" or "chengdu"

    if scenario.startswith("arterial4x4"):
        return f"sumo_simulation/arterial4x4/{scenario}/arterial4x4.sumocfg"
    elif scenario == "chengdu":
        return "sumo_simulation/environments/chengdu/chengdu.sumocfg"
    else:
        raise ValueError(f"Unknown scenario: {scenario}")


def _run_sumo_evaluation(state_file: str, sumocfg: str, tl_id: str, plan: List[Dict], timeout: int) -> Dict:
    """Helper function to run SUMO simulation for one completion.

    Process:
        1. Start SUMO with unique port
        2. Load state file
        3. Execute model's plan: for each phase, setPhase + step for `final` seconds
        4. Collect metrics: passed_vehicles and queue_vehicles
        5. Close SUMO

    Returns:
        {passed_vehicles: int, queue_vehicles: int} or raises exception
    """
    import traci
    import time

    port = random.randint(10000, 60000)
    label = f"reward_{os.getpid()}_{port}"

    try:
        # Find sumo binary
        sumo_binary = "sumo"
        if 'SUMO_HOME' in os.environ:
            candidate = os.path.join(os.environ['SUMO_HOME'], 'bin', 'sumo')
            if os.path.exists(candidate):
                sumo_binary = candidate

        # Start SUMO
        sumo_cmd = [
            sumo_binary,
            "-c", sumocfg,
            "--step-length", "1.0",
            "--no-warnings", "true",
            "--no-step-log",
            "--duration-log.disable",
        ]

        start_time = time.time()
        traci.start(sumo_cmd, port=port, label=label)
        conn = traci.getConnection(label)

        # Load state
        conn.simulation.loadState(state_file)

        # Get controlled lanes
        controlled_lanes = list(set(conn.trafficlight.getControlledLanes(tl_id)))

        # Record vehicles before
        vehicles_before = set()
        for lane in controlled_lanes:
            try:
                vehicles_before.update(conn.lane.getLastStepVehicleIDs(lane))
            except:
                continue

        # Execute plan
        for phase in plan:
            phase_id = phase["phase_id"]
            duration = phase["final"]

            # Set phase
            conn.trafficlight.setPhase(tl_id, phase_id)

            # Step for duration seconds
            for _ in range(duration):
                # Check timeout
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"SUMO simulation timeout ({timeout}s)")

                conn.simulationStep()

        # Record vehicles after
        vehicles_after = set()
        queue_vehicles = 0
        for lane in controlled_lanes:
            try:
                vehicles_after.update(conn.lane.getLastStepVehicleIDs(lane))
                queue_vehicles += conn.lane.getLastStepHaltingNumber(lane)
            except:
                continue

        passed_vehicles = len(vehicles_before - vehicles_after)

        conn.close()

        return {
            "passed_vehicles": passed_vehicles,
            "queue_vehicles": queue_vehicles
        }

    except Exception as e:
        try:
            traci.getConnection(label).close()
        except:
            pass
        raise e


def sumo_simulation_reward(prompts, completions, **kwargs) -> List[float]:
    """L3 - SUMO simulation reward (with baseline normalization).

    Gate: Only executes when L1 format matches AND L2 constraints ALL satisfied.

    For qualifying completions:
        1. Extract phase plan from CyclePlan JSON
        2. Get state_file and tl_id from kwargs
        3. Run SUMO simulation (parallel via ProcessPoolExecutor)
        4. Normalize against baseline metrics
        5. Compute combined score

    Score formula:
        throughput_ratio = model_passed / max(baseline_passed, 1)
        queue_ratio = baseline_queue / max(model_queue, 1)  # lower queue = higher ratio
        combined = throughput_weight * throughput_ratio + queue_weight * queue_ratio
        score = min(combined, 1.0) * sumo_max_score

    If gate not passed: 0.0
    If SUMO crashes/timeout: raise error (per user decision)
    """
    global _sumo_pool, _print_counter

    throughput_weight = _config["sumo_throughput_weight"]
    queue_weight = _config["sumo_queue_weight"]
    sumo_max_score = _config["sumo_max_score"]
    timeout = _config["sumo_timeout_seconds"]

    # Get metadata from kwargs
    state_files = kwargs.get("state_file", [])
    tl_ids = kwargs.get("tl_id", [])

    if not state_files or not tl_ids:
        # No metadata provided, return zeros
        return [0.0] * len(completions)

    scores = []
    tasks = []  # (index, state_file, sumocfg, tl_id, plan)

    for i, (prompt, completion, state_file, tl_id) in enumerate(zip(prompts, completions, state_files, tl_ids)):
        response = completion[0]["content"]

        # Gate check: L1 format
        match = match_format.search(response)
        if not match:
            scores.append(0.0)
            continue

        # Extract plan
        try:
            plan = json.loads(match.group(1))
        except:
            scores.append(0.0)
            continue

        # Gate check: L2 constraints (full satisfaction)
        # Re-parse prompt for constraints
        try:
            prompt_content = prompt[-1]["content"]
            phase_waits_match = re.search(r'"phase_waits"\s*:\s*(\[.*?\])', prompt_content, re.DOTALL)
            if not phase_waits_match:
                scores.append(0.0)
                continue

            phase_waits = json.loads(phase_waits_match.group(1))

            # Check phase order
            expected_phase_ids = [p["phase_id"] for p in phase_waits]
            output_phase_ids = [p.get("phase_id") for p in plan if isinstance(p, dict)]

            if len(output_phase_ids) != len(expected_phase_ids):
                scores.append(0.0)
                continue

            if output_phase_ids != expected_phase_ids:
                scores.append(0.0)
                continue

            # Check green time range for ALL phases
            all_satisfied = True
            for phase in plan:
                if not isinstance(phase, dict):
                    all_satisfied = False
                    break

                phase_id = phase.get("phase_id")
                final = phase.get("final")

                constraint = next((p for p in phase_waits if p["phase_id"] == phase_id), None)
                if not constraint:
                    all_satisfied = False
                    break

                min_green = constraint["min_green"]
                max_green = constraint["max_green"]

                if not (isinstance(final, int) and min_green <= final <= max_green):
                    all_satisfied = False
                    break

            if not all_satisfied:
                scores.append(0.0)
                continue

        except:
            scores.append(0.0)
            continue

        # Passed all gates, prepare SUMO task
        sumocfg = get_sumocfg_for_state(state_file)
        tasks.append((i, state_file, sumocfg, tl_id, plan))
        scores.append(None)  # Placeholder

    # Run SUMO simulations in parallel (if any tasks)
    if tasks:
        # Initialize pool if needed
        if _sumo_pool is None:
            # Use num_generations workers
            num_workers = min(len(tasks), 4)  # Max 4 parallel SUMO instances
            _sumo_pool = ProcessPoolExecutor(max_workers=num_workers)

        # Execute simulations
        simulation_args = [(sf, cfg, tl, pln, timeout) for _, sf, cfg, tl, pln in tasks]

        try:
            results = list(_sumo_pool.map(_run_sumo_evaluation,
                                          [arg[0] for arg in simulation_args],
                                          [arg[1] for arg in simulation_args],
                                          [arg[2] for arg in simulation_args],
                                          [arg[3] for arg in simulation_args],
                                          [arg[4] for arg in simulation_args]))
        except Exception as e:
            # SUMO system error - terminate program per user decision
            raise RuntimeError(f"SUMO simulation failed: {e}")

        # Compute scores with baseline normalization
        for (idx, state_file, _, _, _), result in zip(tasks, results):
            # Get baseline
            baseline = _baseline.get(state_file)
            if not baseline:
                raise RuntimeError(f"Baseline not found for {state_file}")

            baseline_passed = baseline["passed_vehicles"]
            baseline_queue = baseline["queue_vehicles"]

            model_passed = result["passed_vehicles"]
            model_queue = result["queue_vehicles"]

            # Normalize
            throughput_ratio = model_passed / max(baseline_passed, 1)
            queue_ratio = baseline_queue / max(model_queue, 1)

            combined = throughput_weight * throughput_ratio + queue_weight * queue_ratio
            score = min(combined, 1.0) * sumo_max_score

            scores[idx] = score

        # Debug print (every 5 steps)
        _print_counter += 1
        if _print_counter % 5 == 0:
            print("="*50)
            print(f"[SUMO Reward] Sample evaluation:")
            first_task = tasks[0]
            first_result = results[0]
            print(f"  State: {first_task[1]}")
            print(f"  Plan: {first_task[4]}")
            print(f"  Passed: {first_result['passed_vehicles']} (baseline: {baseline_passed})")
            print(f"  Queue: {first_result['queue_vehicles']} (baseline: {baseline_queue})")
            print(f"  Score: {scores[first_task[0]]:.3f}")
            print("="*50)

    # Fill remaining scores with 0.0
    scores = [s if s is not None else 0.0 for s in scores]

    return scores


# ============================================================================
# Think Length Penalty
# ============================================================================

def think_length_reward(completions, **kwargs) -> List[float]:
    """Think length penalty.

    Extracts think content before <end_working_out>, estimates token count,
    and penalizes if too short or too long.

    Note: add_generation_prompt=True prepends <start_working_out>, so completion contains
    content AFTER <start_working_out> until <end_working_out>.

    Token estimation: character count / 2 (rough approximation for Chinese text)

    Penalty formula:
        - If tokens < min_tokens: penalty * (1 - tokens / min_tokens)
        - If tokens > max_tokens: penalty * (tokens / max_tokens - 1)
        - If in range: 0.0 (no penalty)
    """
    min_tokens = _config["think_min_tokens"]
    max_tokens = _config["think_max_tokens"]
    penalty = _config["think_penalty"]
    bonus = _config.get("think_bonus", 0.0)

    scores = []

    for completion in completions:
        response = completion[0]["content"]

        # Find <end_working_out> position
        think_end_pos = response.find("<end_working_out>")
        if think_end_pos == -1:
            scores.append(penalty)
            continue

        # Extract think content (everything before <end_working_out>)
        # Since <start_working_out> is prepended by add_generation_prompt, completion starts right after <start_working_out>
        think_content = response[:think_end_pos]

        # Estimate tokens (char_count / 2)
        think_tokens = len(think_content) / 2

        # Compute score
        if think_tokens < min_tokens:
            score = penalty * (1 - think_tokens / min_tokens)
        elif think_tokens > max_tokens:
            score = penalty * (think_tokens / max_tokens - 1)
        else:
            # In range: linear reward from 0 to bonus
            score = bonus * (think_tokens - min_tokens) / (max_tokens - min_tokens)

        scores.append(score)

    return scores
