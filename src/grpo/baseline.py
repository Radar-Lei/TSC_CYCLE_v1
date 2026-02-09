#!/usr/bin/env python3
"""
Baseline precomputation for GRPO reward normalization.

For each unique state file in grpo_train.jsonl, this script:
1. Loads the SUMO state file
2. Runs the original signal timing for one full cycle
3. Records throughput (passed_vehicles) and queue_vehicles
4. Saves results to baseline.json for reward normalization
"""

import argparse
import json
import os
import random
import sys
import traci
from concurrent.futures import ProcessPoolExecutor


def get_sumocfg_for_state(state_file_relative):
    """Map state file path to its sumocfg.

    Rules (per user decisions):
    - arterial4x4_* -> sumo_simulation/arterial4x4/arterial4x4_*/arterial4x4.sumocfg
    - chengdu -> sumo_simulation/environments/chengdu/chengdu.sumocfg

    Extract scenario name from state_file path:
      outputs/states/arterial4x4_10/state_xxx_nt10.xml -> arterial4x4_10
      outputs/states/chengdu/state_xxx_xxx.xml -> chengdu
    """
    # Parse: outputs/states/<scenario>/<filename>
    parts = state_file_relative.split('/')
    scenario = parts[2]  # e.g. "arterial4x4_10" or "chengdu"

    if scenario.startswith("arterial4x4"):
        return f"sumo_simulation/arterial4x4/{scenario}/arterial4x4.sumocfg"
    elif scenario == "chengdu":
        return "sumo_simulation/environments/chengdu/chengdu.sumocfg"
    else:
        raise ValueError(f"Unknown scenario: {scenario}")


def extract_tl_id(metadata):
    """Extract traffic light ID from metadata."""
    return metadata["tl_id"]


def compute_single_baseline(args_tuple):
    """Worker function for one state file.

    Process:
    1. Start SUMO with the correct sumocfg (headless, no-gui)
    2. Load the saved state file via traci.simulation.loadState()
    3. Get the traffic light's program logic to determine cycle length
       (sum of all phase durations)
    4. Record vehicles before the cycle
    5. Step through one full cycle using the ORIGINAL timing (do NOT change phases)
    6. Record vehicles after, compute passed_vehicles and queue_vehicles
    7. Close SUMO

    Returns dict: {state_file, passed_vehicles, queue_vehicles} or error info
    """
    state_file, sumocfg, tl_id, timeout = args_tuple

    # Use random port to avoid conflicts
    port = random.randint(10000, 60000)

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

        label = f"baseline_{os.getpid()}_{port}"
        traci.start(sumo_cmd, port=port, label=label)
        conn = traci.getConnection(label)

        # Load saved state
        conn.simulation.loadState(state_file)

        # Get cycle length from TL program
        programs = conn.trafficlight.getAllProgramLogics(tl_id)
        phases = programs[0].phases
        cycle_length = int(sum(p.duration for p in phases))

        # Get controlled lanes
        controlled_lanes = list(set(conn.trafficlight.getControlledLanes(tl_id)))

        # Record vehicles before
        vehicles_before = set()
        for lane in controlled_lanes:
            try:
                vehicles_before.update(conn.lane.getLastStepVehicleIDs(lane))
            except:
                continue

        # Run one full cycle with ORIGINAL timing
        for _ in range(cycle_length):
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
            "state_file": state_file,
            "passed_vehicles": passed_vehicles,
            "queue_vehicles": queue_vehicles,
            "cycle_length": cycle_length,
            "status": "ok"
        }
    except Exception as e:
        try:
            traci.getConnection(label).close()
        except:
            pass
        return {
            "state_file": state_file,
            "error": str(e),
            "status": "error"
        }


def main():
    parser = argparse.ArgumentParser(description="Compute SUMO baseline for GRPO reward normalization")
    parser.add_argument("--config", default="config/config.json")
    parser.add_argument("--input", default=None, help="Override grpo_train.jsonl path")
    parser.add_argument("--output", default=None, help="Override baseline.json path")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    # Load config
    with open(args.config) as f:
        config = json.load(f)

    input_path = args.input or os.path.join(config["paths"]["grpo_data_dir"], "grpo_train.jsonl")
    output_path = args.output or config["paths"]["grpo_baseline"]

    # Load samples -- deduplicate by state_file
    seen = set()
    tasks = []
    with open(input_path) as f:
        for line in f:
            sample = json.loads(line)
            sf = sample["metadata"]["state_file"]
            if sf not in seen:
                seen.add(sf)
                tl_id = extract_tl_id(sample["metadata"])
                sumocfg = get_sumocfg_for_state(sf)
                tasks.append((sf, sumocfg, tl_id, args.timeout))

    print(f"[Baseline] Unique state files: {len(tasks)}")
    print(f"[Baseline] Workers: {args.workers}")

    # Run in parallel
    results = {}
    errors = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, result in enumerate(pool.map(compute_single_baseline, tasks)):
            if result["status"] == "ok":
                results[result["state_file"]] = {
                    "passed_vehicles": result["passed_vehicles"],
                    "queue_vehicles": result["queue_vehicles"],
                    "cycle_length": result["cycle_length"]
                }
            else:
                errors += 1
                print(f"[Baseline] ERROR on {result['state_file']}: {result.get('error', 'unknown')}")

            if (i + 1) % 50 == 0:
                print(f"[Baseline] Progress: {i+1}/{len(tasks)} ({errors} errors)")

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"[Baseline] Done. {len(results)}/{len(tasks)} succeeded, {errors} errors")
    print(f"[Baseline] Saved to {output_path}")


if __name__ == "__main__":
    main()
