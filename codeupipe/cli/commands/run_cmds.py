"""``cup run``, ``cup describe``, ``cup graph``, ``cup runs`` commands."""

import json
import sys
import time
from pathlib import Path
from typing import List

from codeupipe import Payload

from .._registry import registry


def setup(sub, reg):
    # cup run <config> [--discover DIR] [--input JSON] [--json] [--record]
    run_parser = sub.add_parser("run", help="Execute a pipeline from a config file")
    run_parser.add_argument("config", help="Path to pipeline config file (.toml or .json)")
    run_parser.add_argument("--discover", metavar="DIR", help="Directory to auto-discover components from")
    run_parser.add_argument("--input", metavar="JSON", dest="input_json", help="Initial payload data as a JSON string")
    run_parser.add_argument("--json", action="store_true", dest="json_output", help="Output result payload as JSON")
    run_parser.add_argument("--record", action="store_true", help="Save run results to .cup/runs/ for history")
    reg.register("run", _handle_run)

    # cup describe <config>
    desc_parser = sub.add_parser("describe", help="Inspect a pipeline config — inputs, outputs, steps, connectors")
    desc_parser.add_argument("config", help="Path to a pipeline config file (.json)")
    reg.register("describe", _handle_describe)

    # cup graph <config> [-o FILE]
    graph_parser = sub.add_parser("graph", help="Visualize a pipeline as a Mermaid diagram")
    graph_parser.add_argument("config", help="Path to pipeline config (.json)")
    graph_parser.add_argument("--output", "-o", help="Write diagram to file instead of stdout")
    reg.register("graph", _handle_graph)

    # cup runs [--pipeline NAME] [--limit N]
    runs_parser = sub.add_parser("runs", help="Show pipeline run history")
    runs_parser.add_argument("--pipeline", help="Filter by pipeline name")
    runs_parser.add_argument("--limit", "-n", type=int, default=20, help="Max records to show (default: 20)")
    reg.register("runs", _handle_runs)


def _handle_run(args):
    try:
        import asyncio

        from codeupipe.registry import Registry
        from codeupipe.core.pipeline import Pipeline

        reg = Registry()
        discover_dir = getattr(args, "discover", None)
        if discover_dir:
            reg.discover(discover_dir, recursive=True)

        config_path = args.config
        pipe = Pipeline.from_config(config_path, registry=reg)

        input_data = {}
        input_json = getattr(args, "input_json", None)
        if input_json:
            input_data = json.loads(input_json)

        t0 = time.monotonic()
        result = asyncio.run(pipe.run(Payload(input_data)))
        duration = time.monotonic() - t0

        config_text = Path(config_path).read_text()
        if config_path.endswith(".json"):
            cfg = json.loads(config_text)
        else:
            cfg = {}
        pipe_name = cfg.get("pipeline", {}).get("name", config_path)

        if getattr(args, "record", False):
            from codeupipe.observe import RunRecord, save_run_record
            record = RunRecord(
                pipe_name, pipe.state,
                input_keys=list(input_data.keys()),
                output_keys=list(result._data.keys()),
                duration=duration,
                success=not pipe.state.has_errors,
                error=str(pipe.state.last_error) if pipe.state.has_errors else None,
            )
            rpath = save_run_record(record)
            print(f"Run recorded: {rpath}", file=sys.stderr)

        if getattr(args, "json_output", False):
            print(json.dumps(dict(result._data)))
        else:
            print(f"Pipeline '{pipe_name}' complete")
            for key, val in result._data.items():
                print(f"  {key}: {val}")
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyError as e:
        print(f"Error: component not found — {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_describe(args):
    try:
        use_json = getattr(args, "json_output", False)
        config_path = args.config

        with open(config_path) as f:
            pipeline_config = json.load(f)

        pipeline = pipeline_config.get("pipeline", {})
        name = pipeline.get("name", "unknown")
        steps = pipeline.get("steps", [])
        require_input = pipeline.get("require_input", [])
        guarantee_output = pipeline.get("guarantee_output", [])

        step_list = []
        for s in steps:
            step_list.append({"name": s.get("name", "?"), "kind": s.get("type", "filter")})

        if use_json:
            result = {
                "name": name, "steps": step_list,
                "require_input": require_input,
                "guarantee_output": guarantee_output,
            }
            print(json.dumps(result, indent=2))
        else:
            print(f"Pipeline: {name}")
            print("  Steps:")
            for i, s in enumerate(step_list, 1):
                print(f"    {i}. {s['name']:24s} ({s['kind']})")
            if require_input:
                print(f"  Requires input:  {', '.join(require_input)}")
            if guarantee_output:
                print(f"  Guarantees output: {', '.join(guarantee_output)}")
        return 0
    except FileNotFoundError:
        print(f"Error: file not found: {args.config}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {args.config}: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_graph(args):
    try:
        from codeupipe.graph import render_graph
        diagram = render_graph(args.config)
        output = getattr(args, "output", None)
        if output:
            Path(output).write_text(diagram)
            print(f"Diagram written to {output}")
        else:
            print(diagram)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_runs(args):
    try:
        from codeupipe.observe import load_run_records
        pipeline_filter = getattr(args, "pipeline", None)
        limit = getattr(args, "limit", 20)
        records = load_run_records(pipeline=pipeline_filter, limit=limit)

        if not records:
            print("No run records found. Use 'cup run --record <config>' to start recording.")
            return 0

        print(f"{'Pipeline':<25} {'Status':<8} {'Duration':<10} {'Steps':<6} {'Timestamp'}")
        print("-" * 80)
        for r in records:
            status = "\u2705" if r.get("success") else "\u274c"
            dur = f"{r.get('duration', 0):.2f}s" if r.get("duration") else "?"
            steps = str(len(r.get("executed", [])))
            ts = r.get("timestamp", "?")[:19]
            print(f"{r.get('pipeline', '?'):<25} {status:<8} {dur:<10} {steps:<6} {ts}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
