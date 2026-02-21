"""
SUMO simulation control module for benchmark runs.

Provides cycle-based simulation control with warmup and pause functionality.
"""

from __future__ import annotations

import math
import os
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Any, TYPE_CHECKING

import traci
from loguru import logger

from TSC_CYCLE.benchmark.config import BenchmarkConfig
from TSC_CYCLE.benchmark.metrics import TrafficMetricsCollector, CycleTrafficMetrics

if TYPE_CHECKING:
    from TSC_CYCLE.benchmark.timing_parser import TimingPlan


def _ensure_sumo_home() -> str:
    """Find SUMO installation and set SUMO_HOME if needed.

    Returns:
        Path to SUMO installation directory

    Raises:
        EnvironmentError: If SUMO cannot be found
    """
    sumo_home = os.getenv("SUMO_HOME")
    if sumo_home:
        candidate = Path(sumo_home).expanduser().resolve()
        if (candidate / "bin" / "sumo").exists():
            return str(candidate)

    candidates = [
        Path("/usr/share/sumo"),
        Path("/opt/homebrew/opt/sumo"),
        Path("/usr/local/opt/sumo"),
    ]
    for candidate in candidates:
        if (candidate / "bin" / "sumo").exists():
            os.environ["SUMO_HOME"] = str(candidate)
            return str(candidate)

    sumo_path = which("sumo")
    if sumo_path:
        candidate = Path(sumo_path).resolve().parents[1]
        os.environ["SUMO_HOME"] = str(candidate)
        return str(candidate)

    raise EnvironmentError("SUMO not found. Set SUMO_HOME or ensure sumo is in PATH.")


def _connect_traci_quiet(
    *,
    host: str,
    port: int,
    label: str,
    proc: subprocess.Popen,
    num_retries: int,
    wait_between_retries: float,
) -> traci.Connection:
    """Connect to TraCI server with retry logic.

    Args:
        host: TraCI server host
        port: TraCI server port
        label: Connection label
        proc: SUMO subprocess
        num_retries: Number of connection retries
        wait_between_retries: Seconds to wait between retries

    Returns:
        TraCI Connection object

    Raises:
        RuntimeError: If connection fails after all retries
    """
    for _ in range(int(num_retries) + 1):
        try:
            return traci.connection.Connection(host, port, proc, None, True, label)
        except (OSError, socket.error):
            if proc.poll() is not None:
                raise RuntimeError("TraCI server already finished") from None
            if wait_between_retries > 0:
                time.sleep(wait_between_retries)
    raise RuntimeError(f"Could not connect to TraCI server in {int(num_retries) + 1} tries")


def _seconds_to_steps(seconds: float, step_length: float) -> int:
    """Convert seconds to simulation steps.

    Args:
        seconds: Time in seconds
        step_length: Simulation step length in seconds

    Returns:
        Number of simulation steps (rounded up)
    """
    step = float(step_length) if step_length else 1.0
    return max(0, int(math.ceil(float(seconds) / step)))


@dataclass
class CycleState:
    """State information for a simulation cycle.

    Attributes:
        cycle_index: Current cycle index (0-based)
        cycle_start_time: Simulation time when current cycle started
        sim_time: Current simulation time
        is_warmup_complete: Whether warmup period has completed
        is_cycle_end: Whether we've reached the end of a cycle
        is_done: Whether simulation has completed
    """
    cycle_index: int
    cycle_start_time: float
    sim_time: float
    is_warmup_complete: bool
    is_cycle_end: bool
    is_done: bool


class BenchmarkSimulation:
    """SUMO simulation controller with cycle-based pausing.

    Provides lifecycle management for SUMO simulations with support for
    warmup periods and cycle-by-cycle execution for LLM decision points.

    Attributes:
        config: Benchmark configuration
        sumocfg_path: Path to SUMO configuration file
        seed: Random seed for reproducibility
        gui: Whether to show SUMO GUI
    """

    def __init__(
        self,
        config: BenchmarkConfig,
        sumocfg_path: str | Path,
        seed: int = 42,
        gui: bool = False,
    ):
        """Initialize simulation controller.

        Args:
            config: Benchmark configuration
            sumocfg_path: Path to .sumocfg file
            seed: Random seed for reproducibility
            gui: Whether to show SUMO GUI
        """
        self._config = config
        self._sumocfg_path = Path(sumocfg_path).resolve()
        self._seed = int(seed)
        self._gui = bool(gui)

        self._conn: traci.Connection | None = None
        self._cycle_index: int = 0
        self._cycle_start_time: float = 0.0
        self._is_warmup_complete: bool = False
        self._is_done: bool = False
        self._label = f"benchmark_{seed}_{id(self)}"

    @property
    def conn(self) -> traci.Connection:
        """Get TraCI connection.

        Returns:
            Active TraCI connection

        Raises:
            RuntimeError: If simulation not started
        """
        if self._conn is None:
            raise RuntimeError("Simulation not started. Call start() first.")
        return self._conn

    @property
    def cycle_index(self) -> int:
        """Current cycle index (0-based)."""
        return self._cycle_index

    @property
    def sim_time(self) -> float:
        """Current simulation time in seconds."""
        if self._conn is None:
            return 0.0
        return float(self._conn.simulation.getTime())

    @property
    def is_done(self) -> bool:
        """Whether simulation has completed."""
        return self._is_done

    def start(self) -> None:
        """Start SUMO simulation and run warmup period.

        Launches SUMO with TraCI connection, runs the warmup period,
        and then pauses ready for cycle-by-cycle execution.

        Raises:
            RuntimeError: If simulation already started
            FileNotFoundError: If sumocfg file not found
            EnvironmentError: If SUMO not found
        """
        if self._conn is not None:
            raise RuntimeError("Simulation already started")

        sumo_home = _ensure_sumo_home()
        sumo_binary = "sumo-gui" if self._gui else "sumo"
        sumo_exe = str(Path(sumo_home) / "bin" / sumo_binary)

        if not self._sumocfg_path.exists():
            raise FileNotFoundError(f"sumocfg not found: {self._sumocfg_path}")

        sumo_cmd = [
            sumo_exe,
            "-c", str(self._sumocfg_path),
            "--seed", str(self._seed),
            "--step-length", str(self._config.step_length),
            "--no-warnings", "true",
            "--start",
            "--quit-on-end",
        ]

        logger.info("Starting SUMO simulation: {}", " ".join(sumo_cmd))

        if traci.connection.has(self._label):
            raise RuntimeError(f"TraCI connection '{self._label}' is already active")

        retry_delay_s = float(os.getenv("BENCHMARK_TRACI_RETRY_DELAY_S", "0.05"))
        num_retries = int(os.getenv("BENCHMARK_TRACI_NUM_RETRIES", "1200"))

        sumo_port = traci.getFreeSocketPort()
        sumo_cmd = sumo_cmd + ["--remote-port", str(sumo_port)]
        sumo_proc = subprocess.Popen(sumo_cmd, cwd=str(self._sumocfg_path.parent))

        try:
            conn = _connect_traci_quiet(
                host="localhost",
                port=sumo_port,
                label=self._label,
                proc=sumo_proc,
                num_retries=num_retries,
                wait_between_retries=retry_delay_s,
            )
            conn.getVersion()
            self._conn = conn
        except Exception:
            try:
                sumo_proc.terminate()
                sumo_proc.wait(timeout=5)
            except Exception:
                try:
                    sumo_proc.kill()
                except Exception:
                    pass
            raise

        # Run warmup period
        warmup_steps = _seconds_to_steps(self._config.warmup_seconds, self._config.step_length)
        if warmup_steps > 0:
            logger.info("Running warmup: {} steps ({} seconds)", warmup_steps, self._config.warmup_seconds)
            for _ in range(warmup_steps):
                self._conn.simulationStep()

        # Initialize cycle state after warmup
        self._cycle_start_time = float(self._conn.simulation.getTime())
        self._cycle_index = 0
        self._is_warmup_complete = True
        self._is_done = False

        logger.info("Warmup complete. Simulation ready at time {:.1f}s", self._cycle_start_time)

    def run_cycle(self) -> CycleState:
        """Run simulation for one cycle duration.

        Advances simulation by cycle_duration seconds and returns
        the cycle state. If simulation_seconds is reached, sets is_done=True.

        Returns:
            CycleState with current cycle information

        Raises:
            RuntimeError: If simulation not started
        """
        if self._conn is None:
            raise RuntimeError("Simulation not started. Call start() first.")

        if self._is_done:
            return CycleState(
                cycle_index=self._cycle_index,
                cycle_start_time=self._cycle_start_time,
                sim_time=self.sim_time,
                is_warmup_complete=self._is_warmup_complete,
                is_cycle_end=False,
                is_done=True,
            )

        # Calculate steps for this cycle
        cycle_steps = _seconds_to_steps(self._config.cycle_duration, self._config.step_length)

        # Run simulation steps for one cycle
        for _ in range(cycle_steps):
            self._conn.simulationStep()

            # Check if simulation has ended
            try:
                if int(self._conn.simulation.getMinExpectedNumber()) <= 0:
                    self._is_done = True
                    break
            except Exception:
                pass

            # Check if we've reached simulation_seconds
            current_time = float(self._conn.simulation.getTime())
            if current_time >= self._config.simulation_seconds:
                logger.info("Reached simulation_seconds limit: {}s >= {}s, ending simulation",
                           current_time, self._config.simulation_seconds)
                self._is_done = True
                break

        # Update cycle state
        cycle_end_time = self.sim_time
        is_cycle_end = True

        state = CycleState(
            cycle_index=self._cycle_index,
            cycle_start_time=self._cycle_start_time,
            sim_time=cycle_end_time,
            is_warmup_complete=self._is_warmup_complete,
            is_cycle_end=is_cycle_end,
            is_done=self._is_done,
        )

        # Advance to next cycle
        self._cycle_index += 1
        self._cycle_start_time = cycle_end_time

        logger.debug(
            "Cycle {} complete at time {:.1f}s, done={}",
            state.cycle_index,
            state.sim_time,
            state.is_done,
        )

        return state

    def apply_timing_plan(
        self,
        tl_id: str,
        plan: "TimingPlan",
    ) -> CycleTrafficMetrics:
        """Apply a timing plan to a traffic light.

        Executes the timing plan by setting each phase and running
        the simulation for the specified duration. Collects traffic
        metrics during execution.

        Implementation (from CONTEXT.md):
        1. Set phase using traci.trafficlight.setPhase
        2. Set duration using traci.trafficlight.setPhaseDuration
        3. Run simulation for duration seconds
        4. Collect metrics at each simulation step

        Args:
            tl_id: Traffic light ID
            plan: TimingPlan containing phases with durations

        Returns:
            CycleTrafficMetrics containing passed_vehicles, avg_queue_vehicles,
            total_delay, and per-second samples

        Raises:
            RuntimeError: If simulation not started

        Example:
            >>> from TSC_CYCLE.benchmark.timing_parser import TimingPlan, PhaseTiming
            >>> plan = TimingPlan(phases=[
            ...     PhaseTiming(phase_id=0, final=30),
            ...     PhaseTiming(phase_id=1, final=25),
            ... ])
            >>> metrics = sim.apply_timing_plan('nt1', plan)
            >>> print(f"Passed: {metrics.passed_vehicles}")
        """
        if self._conn is None:
            raise RuntimeError("Simulation not started. Call start() first.")

        # Create metrics collector
        collector = TrafficMetricsCollector(self._conn, tl_id)
        collector.start_cycle()

        logger.info(
            "Applying timing plan to {}: {} phases",
            tl_id,
            len(plan.phases)
        )

        for phase in plan.phases:
            # Set phase using SUMO index (not LLM-friendly phase_id)
            self._conn.trafficlight.setPhase(tl_id, phase.sumo_phase_index)

            # Set duration
            self._conn.trafficlight.setPhaseDuration(tl_id, phase.final)

            # Run for duration seconds
            steps = _seconds_to_steps(phase.final, self._config.step_length)
            for _ in range(steps):
                self._conn.simulationStep()
                collector.sample()  # Sample at each step

                # Check if simulation has ended
                try:
                    if int(self._conn.simulation.getMinExpectedNumber()) <= 0:
                        self._is_done = True
                        break
                except Exception:
                    pass

                # Check if we've reached simulation_seconds
                current_time = float(self._conn.simulation.getTime())
                if current_time >= self._config.simulation_seconds:
                    logger.info("Reached simulation_seconds limit: {}s >= {}s, ending simulation",
                               current_time, self._config.simulation_seconds)
                    self._is_done = True
                    break

            if self._is_done:
                break

        # Return metrics
        metrics = collector.finish_cycle()
        logger.debug(
            "Timing plan applied to {} at time {:.1f}s, passed={}, queue={:.1f}, delay={:.1f}",
            tl_id, self.sim_time,
            metrics.passed_vehicles, metrics.avg_queue_vehicles, metrics.total_delay
        )
        return metrics

    def get_state(self) -> dict[str, Any]:
        """Get current simulation state.

        Returns:
            Dictionary containing:
            - sim_time: Current simulation time
            - cycle_index: Current cycle index
            - phase: Current traffic light phase for each TLS
            - vehicle_counts: Vehicle statistics

        Raises:
            RuntimeError: If simulation not started
        """
        if self._conn is None:
            raise RuntimeError("Simulation not started. Call start() first.")

        sim_time = float(self._conn.simulation.getTime())

        # Collect TLS state
        tls_ids = []
        try:
            tls_ids = list(self._conn.trafficlight.getIDList())
        except Exception:
            pass

        tls_state = {}
        for tls_id in tls_ids:
            try:
                phase = int(self._conn.trafficlight.getPhase(tls_id))
                state_str = str(self._conn.trafficlight.getRedYellowGreenState(tls_id))
            except Exception:
                phase = 0
                state_str = ""

            # Get vehicle counts on controlled lanes
            vehicle_count = 0
            halting_count = 0
            try:
                controlled_links = self._conn.trafficlight.getControlledLinks(tls_id)
                lanes = set()
                for link_group in controlled_links:
                    for link in link_group:
                        if link and link[0]:
                            lanes.add(str(link[0]))
                for lane_id in lanes:
                    vehicle_count += int(self._conn.lane.getLastStepVehicleNumber(lane_id))
                    halting_count += int(self._conn.lane.getLastStepHaltingNumber(lane_id))
            except Exception:
                pass

            tls_state[tls_id] = {
                "phase": phase,
                "state": state_str,
                "vehicle_count": vehicle_count,
                "halting_count": halting_count,
            }

        # Get global vehicle statistics
        total_vehicles = 0
        total_halting = 0
        try:
            total_vehicles = len(self._conn.vehicle.getIDList())
        except Exception:
            pass
        try:
            total_halting = int(self._conn.simulation.getStoppedVehicleNumber())
        except Exception:
            pass

        return {
            "sim_time": sim_time,
            "cycle_index": self._cycle_index,
            "cycle_start_time": self._cycle_start_time,
            "is_warmup_complete": self._is_warmup_complete,
            "is_done": self._is_done,
            "total_vehicles": total_vehicles,
            "total_halting": total_halting,
            "tls": tls_state,
        }

    def close(self) -> None:
        """Close SUMO simulation and TraCI connection."""
        if self._conn is None:
            return
        try:
            self._conn.close()
        except Exception as e:
            logger.warning("Error closing TraCI connection: {}", e)
        finally:
            self._conn = None
            logger.info("Simulation closed")


def discover_scenarios(environments_dir: str | Path) -> list[str]:
    """Discover available SUMO scenarios in environments directory.

    Scans the environments directory for subdirectories containing .sumocfg files.

    Args:
        environments_dir: Path to environments directory

    Returns:
        List of scenario names (directory names containing .sumocfg files)
    """
    env_path = Path(environments_dir)

    if not env_path.exists():
        logger.warning("Environments directory not found: {}", env_path)
        return []

    scenarios = []
    for item in env_path.iterdir():
        if item.is_dir():
            # Check if directory contains a .sumocfg file
            sumocfg_files = list(item.glob("*.sumocfg"))
            if sumocfg_files:
                scenarios.append(item.name)

    return sorted(scenarios)


def get_sumocfg_path(environments_dir: str | Path, scenario_name: str) -> Path | None:
    """Find .sumocfg file for a scenario.

    Args:
        environments_dir: Path to environments directory
        scenario_name: Name of the scenario (directory name)

    Returns:
        Path to .sumocfg file, or None if not found
    """
    env_path = Path(environments_dir)
    scenario_dir = env_path / scenario_name

    if not scenario_dir.exists() or not scenario_dir.is_dir():
        return None

    sumocfg_files = list(scenario_dir.glob("*.sumocfg"))

    if not sumocfg_files:
        return None

    # Return first .sumocfg file found
    return sumocfg_files[0].resolve()
