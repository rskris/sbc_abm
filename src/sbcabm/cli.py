"""Command-line interface: ``sbcabm``.

Subcommands:
    info       show the resolved configuration and available pipeline stages
    run        run the pipeline (all configured stages, or a subset via --stages)
    preflight  verify live-data readiness: host reachability + variable scheme
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import load_config
from .pipeline import build_pipeline

_DEFAULT_CONFIG = "configs/settings.yaml"


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _cmd_info(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    pipeline = build_pipeline(config)
    implemented = set(pipeline.registry.names())

    print(f"Region        : {config.region.name} (FIPS {config.region.county_geoid})")
    print(f"Random seed   : {config.random_seed}")
    print(f"ACS vintage   : {config.data.acs_year}")
    print(f"Zone system   : {config.zones.system}")
    print(f"Network access: {'on' if config.data.allow_network else 'off'}")
    print("\nPipeline stages:")
    for stage in config.stages:
        mark = "implemented" if stage in implemented else "planned"
        print(f"  - {stage:<12} [{mark}]")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    pipeline = build_pipeline(config)
    stages = args.stages.split(",") if args.stages else None
    store = pipeline.run(stages)

    out_dir = Path(config.paths.output_dir)
    if args.write:
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in store.names():
            path = out_dir / f"{name}.csv"
            store.get(name).to_csv(path, index=False)
            print(f"wrote {path}")

    print("\nData store tables after run:")
    for name in store.names():
        print(f"  - {name:<22} {len(store.get(name)):>8d} rows")
    return 0


def _cmd_preflight(args: argparse.Namespace) -> int:
    from .data.preflight import run_preflight

    config = load_config(args.config)
    report, ok = run_preflight(config)
    failures = report[~report["reachable"]]
    print(report.to_string(index=False))
    print(f"\npreflight: {'PASS' if ok else 'FAIL'}"
          f" ({len(failures)} of {len(report)} checks failing)")
    if not ok and len(failures):
        print("Blocked hosts must be added to this environment's network "
              "allowlist before a live run (see docs/bmad/stories/7.5).")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sbcabm", description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.add_argument(
        "-c", "--config", default=_DEFAULT_CONFIG, help="path to the YAML config"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="show configuration and stages")
    p_info.set_defaults(func=_cmd_info)

    p_run = sub.add_parser("run", help="run the pipeline")
    p_run.add_argument(
        "--stages", help="comma-separated subset of stages (default: all configured)"
    )
    p_run.add_argument(
        "--write", action="store_true", help="write data-store tables to the output dir"
    )
    p_run.set_defaults(func=_cmd_run)

    p_pre = sub.add_parser("preflight", help="verify live-data readiness")
    p_pre.set_defaults(func=_cmd_preflight)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
