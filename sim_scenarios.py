from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from drone_sim import DroneSimulation


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    duration_s: float
    final_phase: str
    final_x: float
    final_y: float
    final_altitude_m: float
    battery_percent: float
    events_count: int
    max_distance_from_home_m: float
    notes: str


def run_all(log_dir: str = "logs") -> list[ScenarioResult]:
    Path(log_dir).mkdir(exist_ok=True)
    results = [
        run_nominal_patrol(),
        run_return_home(),
        run_abort(),
        run_manual_override(),
        run_high_wind_return(),
        run_camera_detection_injection(),
    ]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = Path(log_dir) / f"sim_scenarios_{stamp}.json"
    csv_path = Path(log_dir) / f"sim_scenarios_{stamp}.csv"
    json_path.write_text(json.dumps([asdict(result) for result in results], indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for result in results:
            writer.writerow(asdict(result))
    print_summary(results, json_path, csv_path)
    return results


def run_nominal_patrol() -> ScenarioResult:
    sim = fresh_sim()
    sim.command("start")
    max_dist = run_ticks(sim, seconds=35)
    state = sim.snapshot()
    passed = state["phase"] in {"PATROL", "HOLD", "RETURN_HOME"} and state["altitude_m"] >= 15
    return result("nominal_patrol", passed, 35, state, max_dist, "Drone should take off and begin patrol.")


def run_return_home() -> ScenarioResult:
    sim = fresh_sim()
    sim.command("start")
    run_ticks(sim, seconds=10)
    sim.command("rth")
    max_dist = run_ticks(sim, seconds=45)
    state = sim.snapshot()
    distance_home = distance_to_home(sim)
    passed = state["phase"] in {"LANDING", "LANDED"} or distance_home < 2.5
    return result("return_home", passed, 55, state, max_dist, f"Distance to home: {distance_home:.2f} m.")


def run_abort() -> ScenarioResult:
    sim = fresh_sim()
    sim.command("start")
    run_ticks(sim, seconds=8)
    sim.command("abort")
    max_dist = run_ticks(sim, seconds=5)
    state = sim.snapshot()
    passed = state["phase"] == "ABORTED" and state["emergency_stop"]
    return result("abort", passed, 13, state, max_dist, "Emergency stop should dominate mission state.")


def run_manual_override() -> ScenarioResult:
    sim = fresh_sim()
    sim.command("start")
    run_ticks(sim, seconds=8)
    before = sim.snapshot()
    sim.command("manual_override", {"enabled": True})
    run_ticks(sim, seconds=4)
    held = sim.snapshot()
    sim.command("manual_override", {"enabled": False})
    run_ticks(sim, seconds=4)
    after = sim.snapshot()
    passed = held["manual_override"] and held["phase"] == "HOLD" and not after["manual_override"]
    notes = f"Phase before={before['phase']} held={held['phase']} after={after['phase']}."
    return result("manual_override", passed, 16, after, max_path_distance(sim), notes)


def run_high_wind_return() -> ScenarioResult:
    sim = fresh_sim()
    sim.command("start")
    run_ticks(sim, seconds=12)
    sim.command("wind", {"speed_mps": 16, "gust_mps": 4})
    max_dist = run_ticks(sim, seconds=8)
    state = sim.snapshot()
    passed = state["phase"] in {"RETURN_HOME", "LANDING", "LANDED"}
    return result("high_wind_return", passed, 20, state, max_dist, "Unsafe wind should trigger return-home.")


def run_camera_detection_injection() -> ScenarioResult:
    sim = fresh_sim()
    sim.command("start")
    run_ticks(sim, seconds=8)
    sim.command("inject_detection", {"kind": "vehicle"})
    run_ticks(sim, seconds=1)
    state = sim.snapshot()
    passed = bool(state["events"]) and state["events"][-1]["kind"] == "vehicle"
    return result("camera_detection_injection", passed, 9, state, max_path_distance(sim), "Injected camera event should appear in alerts/events.")


def fresh_sim() -> DroneSimulation:
    sim = DroneSimulation("mission_config.json")
    sim.config["wind"]["speed_mps"] = 0
    sim.config["wind"]["gust_mps"] = 0
    sim.state.wind_speed_mps = 0
    sim.state.wind_gust_mps = 0
    return sim


def run_ticks(sim: DroneSimulation, seconds: float, dt: float = 0.2) -> float:
    ticks = int(seconds / dt)
    max_dist = 0.0
    for _ in range(ticks):
        sim._tick(dt)
        max_dist = max(max_dist, distance_to_home(sim))
    return max_dist


def result(name: str, passed: bool, duration: float, state: dict, max_dist: float, notes: str) -> ScenarioResult:
    return ScenarioResult(
        name=name,
        passed=passed,
        duration_s=duration,
        final_phase=state["phase"],
        final_x=round(state["x"], 2),
        final_y=round(state["y"], 2),
        final_altitude_m=round(state["altitude_m"], 2),
        battery_percent=round(state["battery_percent"], 2),
        events_count=len(state["events"]),
        max_distance_from_home_m=round(max_dist, 2),
        notes=notes,
    )


def distance_to_home(sim: DroneSimulation) -> float:
    return math.hypot(sim.state.x - sim.home.x, sim.state.y - sim.home.y)


def max_path_distance(sim: DroneSimulation) -> float:
    return max((math.hypot(point["x"] - sim.home.x, point["y"] - sim.home.y) for point in sim.state.path), default=0.0)


def print_summary(results: list[ScenarioResult], json_path: Path, csv_path: Path) -> None:
    passed = sum(1 for result in results if result.passed)
    print(f"Simulation scenario results: {passed}/{len(results)} passed")
    for item in results:
        status = "PASS" if item.passed else "FAIL"
        print(f"{status} {item.name}: final={item.final_phase}, alt={item.final_altitude_m}m, events={item.events_count}, {item.notes}")
    print(f"JSON report: {json_path}")
    print(f"CSV report: {csv_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run fast headless simulator scenario tests")
    parser.add_argument("--log-dir", default="logs")
    args = parser.parse_args()
    run_all(args.log_dir)


if __name__ == "__main__":
    main()
