from __future__ import annotations

import argparse

from gw2_progression.advice.player_advice import PlayerAdviceEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate player-facing GW2 craft-vs-buy advice.")
    parser.add_argument("feasibility_report", help="Path to account_craft_feasibility_*.json")
    parser.add_argument("--output-dir", default="data/knowledge_acquisition", help="Directory for Markdown and JSON outputs")
    args = parser.parse_args()

    result = PlayerAdviceEngine().from_file(args.feasibility_report)
    paths = result.write(args.output_dir)
    print(f"markdown_path={paths['markdown_path']}")
    print(f"json_path={paths['json_path']}")


if __name__ == "__main__":
    main()
