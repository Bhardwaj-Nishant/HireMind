"""
Entrypoint for intelligence-service. Runs one matching or generation cycle
and exits — schedule with cron, same pattern as ingestion-service.

Usage:
    python -m app.main match
    python -m app.main match --limit 20
    python -m app.main generate
    python -m app.main generate --limit 10 --min-score 70
"""
import argparse

from shared.generation.generator import MIN_SCORE_TO_GENERATE, run_generation_cycle
from shared.matching.matcher import run_matching_cycle

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    match_parser = subparsers.add_parser("match", help="Score unmatched jobs against the resume")
    match_parser.add_argument("--limit", type=int, default=50)

    generate_parser = subparsers.add_parser(
        "generate", help="Generate resume/cover letter/email drafts for good matches"
    )
    generate_parser.add_argument("--limit", type=int, default=20)
    generate_parser.add_argument("--min-score", type=float, default=MIN_SCORE_TO_GENERATE)

    args = parser.parse_args()

    if args.command == "match":
        run_matching_cycle(limit=args.limit)
    elif args.command == "generate":
        run_generation_cycle(limit=args.limit, min_score=args.min_score)