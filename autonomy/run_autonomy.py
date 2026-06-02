from __future__ import annotations

import argparse
import logging
import time

from autonomy.config_loader import load_mission_config
from autonomy.mission_logger import MissionLogger
from autonomy.mission_manager import MissionManager
from autonomy.px4_controller_interface import PX4ControllerInterface


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PX4 Offboard autonomy mission")
    parser.add_argument("--config", default="config/autonomy.yaml")
    parser.add_argument("--log-dir", default="logs")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = load_mission_config(args.config)
    controller = PX4ControllerInterface()
    logger = MissionLogger(args.log_dir)
    manager = MissionManager(controller=controller, config=config, mission_logger=logger)
    manager.start()
    period = 1.0 / config.control_rate_hz

    try:
        while True:
            started = time.monotonic()
            controller.spin_once(timeout_sec=0.0)
            manager.tick(now_s=started, dt_s=period)
            elapsed = time.monotonic() - started
            time.sleep(max(0.0, period - elapsed))
    finally:
        logger.close()


if __name__ == "__main__":
    main()

