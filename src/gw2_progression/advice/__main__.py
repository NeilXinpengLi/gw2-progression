from __future__ import annotations

import argparse
import json

from gw2_progression.advice.player_advice import PlayerAdviceEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate player-facing GW2 craft-vs-buy advice.")
    parser.add_argument("feasibility_report", help="Path to account_craft_feasibility_*.json")
    parser.add_argument("--output-dir", default="data/knowledge_acquisition", help="Directory for Markdown and JSON outputs")
    parser.add_argument("--player-goal", default="", help="Player goal, for example gold_profit, beginner_progress, legendary_progress")
    parser.add_argument("--account-stage", default="", help="Account stage override, for example beginner, developing, established")
    parser.add_argument("--context-json", default="", help="JSON object with snapshot_delta, market_risk, or other context fields")
    parser.add_argument("--include-explanations", action="store_true", help="Render context-aware why/risk explanations")
    parser.add_argument("--report-language", default="", help="Report explanation language: en (default) or zh")
    parser.add_argument("--llm-explanation-layer", default="", help="Use deterministic_template or provider/openai_compatible")
    parser.add_argument("--llm-provider-key-file", default="", help="Optional provider key file path; value is not written to output")
    parser.add_argument("--llm-provider-model", default="", help="Optional provider model override, for example agnes-2.0-flash")
    parser.add_argument("--llm-provider-limit", type=int, default=3, help="Maximum recommendations to rewrite through the LLM provider")
    args = parser.parse_args()

    context = json.loads(args.context_json) if args.context_json else {}
    if not isinstance(context, dict):
        raise SystemExit("--context-json must be a JSON object")
    context.update(
        {
            "player_goal": args.player_goal or context.get("player_goal", ""),
            "account_stage": args.account_stage or context.get("account_stage", ""),
            "include_explanations": args.include_explanations or bool(context.get("include_explanations", False)),
            "report_language": args.report_language or context.get("report_language", ""),
            "llm_explanation_layer": args.llm_explanation_layer or context.get("llm_explanation_layer", ""),
            "llm_provider_key_file": args.llm_provider_key_file or context.get("llm_provider_key_file", ""),
            "llm_provider_model": args.llm_provider_model or context.get("llm_provider_model", ""),
            "llm_provider_limit": args.llm_provider_limit if args.llm_provider_limit is not None else context.get("llm_provider_limit", 3),
        }
    )

    result = PlayerAdviceEngine().from_file(args.feasibility_report, context=context)
    paths = result.write(args.output_dir)
    print(f"markdown_path={paths['markdown_path']}")
    print(f"json_path={paths['json_path']}")


if __name__ == "__main__":
    main()
