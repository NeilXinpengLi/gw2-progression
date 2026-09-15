#!/usr/bin/env python3
"""Entry point for GW2 Data Factory Docker services.

Usage:
    python -m src.gw2_progression.data_acquisition.factory_entry --mode collector
    python -m src.gw2_progression.data_acquisition.factory_entry --mode dgsk
    python -m src.gw2_progression.data_acquisition.factory_entry --mode oosk
    python -m src.gw2_progression.data_acquisition.factory_entry --mode inference
    python -m src.gw2_progression.data_acquisition.factory_entry --mode flywheel
"""

from __future__ import annotations

import argparse
import logging
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("factory_entry")


def main() -> None:
    parser = argparse.ArgumentParser(description="GW2 Data Factory Service")
    parser.add_argument("--mode", type=str, default="collector", choices=["collector", "dgsk", "oosk", "inference", "flywheel"])
    parser.add_argument("--interval", type=int, default=60, help="Polling interval in seconds")
    args = parser.parse_args()

    from gw2_progression.cognitive_os.engine import get_cognitive_os

    cos = get_cognitive_os()
    cos.initialize({"gold": 0, "inventory": {}, "achievements": []})
    factory = cos.data_factory
    factory.start()

    logger.info("Data Factory started in mode=%s (interval=%ds)", args.mode, args.interval)

    def collector_loop():
        while True:
            logger.info("Collecting all sources...")
            results = factory.collect_all()
            logger.info("Collected %d sources", len(results))
            time.sleep(args.interval)

    def dgsk_loop():
        while True:
            logger.info("Building DGSK graph...")
            result = factory.build_graph()
            logger.info("Graph: %d nodes, %d edges", result.total_nodes, result.total_edges)
            time.sleep(args.interval)

    def oosk_loop():
        while True:
            logger.info("Running simulation step...")
            cos.step()
            logger.info("Simulation t=%d", cos.temporal.t)
            time.sleep(args.interval)

    def inference_loop():
        while True:
            logger.info("Running behavior inference...")
            result = cos.classify_behavior()
            logger.info("Dominant archetype: %s", result.get("dominant_archetype", "unknown"))
            time.sleep(args.interval)

    def flywheel_loop():
        logger.info("Starting data flywheel (autonomous loop)...")
        factory.run_flywheel(iterations=0)  # infinite

    loops = {
        "collector": collector_loop,
        "dgsk": dgsk_loop,
        "oosk": oosk_loop,
        "inference": inference_loop,
        "flywheel": flywheel_loop,
    }

    try:
        loops[args.mode]()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        factory.stop()


if __name__ == "__main__":
    main()
