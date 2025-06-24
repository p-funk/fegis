#!/usr/bin/env python3
"""
Enhanced MCP log reader for analyzing fegis server interactions.

Parses MCP protocol messages from log files and formats tool calls and responses
for better visibility into search operations and memory interactions.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from textwrap import shorten


def parse_log_line(line):
    m = re.search(r"Message from (client|server): (.*?) \{ metadata", line)
    if not m:
        return None
    return m.group(1), json.loads(m.group(2))


def _pretty(value, width=80, full_output=False):
    """Pretty format a value with optional truncation."""
    if isinstance(value, str) and not full_output:
        return shorten(value, width=width, placeholder="…")
    return value


def format_tool_call(data, full_output=False):
    """Format a tool call message."""
    params = data.get("params", {})
    tool_name = params.get("name", "unknown")
    args = params.get("arguments", {})

    # Store query for search tools so response can use it
    if tool_name == "SearchMemory" and "query" in args:
        format_response._last_search_query = args["query"]

    # Add timestamp for better debugging
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    print(f"🔧 [{timestamp}] TOOL CALL: {tool_name}")

    if full_output:
        print(json.dumps(args, indent=2, ensure_ascii=False))
    else:
        for k, v in args.items():
            print(f"  {k}: {_pretty(v, full_output=full_output)}")
    return True  # always printed


def format_search_results(obj, full_output=False):
    """Format legacy search results."""
    q = obj.get("query", "<no query>")
    results = obj.get("results", [])
    print(f'📋 SEARCH: "{q}" -> {len(results)} results')
    for idx, item in enumerate(results, 1):
        title = item.get("title") or item.get("Title", "Untitled")
        print(f"  {idx}. {title}")
        if full_output:
            print(json.dumps(item, indent=4, ensure_ascii=False))
            print()
        else:
            for k, v in item.items():
                if k.lower() in {"title"}:
                    continue
                print(f"     {k}: {_pretty(v, full_output=full_output)}")
            if idx != len(results):
                print()


def format_new_search_results(search_results_str, query_from_call, full_output=False):
    """Format search results from the new component-based system."""
    try:
        results = json.loads(search_results_str)
        # Try to extract query from first result if available
        if not query_from_call or query_from_call == "<no query>":
            if results and isinstance(results, list) and len(results) > 0:
                first_result = results[0]
                if isinstance(first_result, dict) and "query" in first_result:
                    query_from_call = first_result["query"]

        print(f'🔎 SEARCH: "{query_from_call}" -> {len(results)} results')
        for idx, item in enumerate(results, 1):
            title = item.get("title", "Untitled")
            print(f"  {idx}. {title}")
            if full_output:
                print(json.dumps(item, indent=4, ensure_ascii=False))
                print()
            else:
                for k, v in item.items():
                    if k.lower() == "title":  # Skip title since we already showed it
                        continue
                    print(f"     {k}: {_pretty(v, full_output=full_output)}")
                if idx != len(results):
                    print()
    except json.JSONDecodeError:
        print(
            f"📋 SEARCH RESPONSE: {_pretty(search_results_str, full_output=full_output)}"
        )


def format_response(data, full_output=False):
    """Format a response message."""
    content = data.get("result", {}).get("content")
    if not content:
        return False
    text = content[0].get("text", "").strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        # Non-JSON response; print compact
        print("✅ RESPONSE:", _pretty(text, width=1000, full_output=full_output))
        return True

    # Check for new search result format
    if "search_results" in obj:
        # Extract query from the last search call (stored globally)
        query = getattr(format_response, "_last_search_query", "<no query>")
        format_new_search_results(obj["search_results"], query, full_output)
    # Legacy search response format
    elif "results" in obj and isinstance(obj["results"], list):
        format_search_results(obj, full_output)
    else:
        print("✅ RESPONSE:")
        if full_output:
            print(json.dumps(obj, indent=2, ensure_ascii=False))
        else:
            for k, v in obj.items():
                print(f"  {k}: {_pretty(v, full_output=full_output)}")
    return True


def handle(data_tuple, full_output=False):
    """Handle a parsed log message."""
    direction, payload = data_tuple
    printed = False
    if direction == "client" and payload.get("method") == "tools/call":
        printed = format_tool_call(payload, full_output)
    elif direction == "server":
        printed = format_response(payload, full_output)
    if printed:
        print()


def tail_file(file_path, full_output=False):
    """Follow a log file in real-time."""
    with open(file_path) as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if line:
                tpl = parse_log_line(line)
                if tpl:
                    handle(tpl, full_output)
            else:
                time.sleep(0.1)


def read_file(file_path, full_output=False):
    """Read entire log file."""
    with open(file_path) as f:
        for line in f:
            tpl = parse_log_line(line)
            if tpl:
                handle(tpl, full_output)


def create_parser():
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Enhanced MCP log reader for analyzing fegis server interactions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Read default log file
  %(prog)s mylog.log                 # Read specific log file
  %(prog)s -f                        # Follow default log file
  %(prog)s -f mylog.log              # Follow specific log file
  %(prog)s --full mylog.log          # Show full JSON output
  %(prog)s -f --full mylog.log       # Follow with full output
        """,
    )

    parser.add_argument(
        "logfile",
        nargs="?",
        default="~/Library/Logs/Claude/mcp-server-fegis.log",
        help="Log file to read (default: ~/Library/Logs/Claude/mcp-server-fegis.log)",
    )

    parser.add_argument(
        "-f",
        "--follow",
        action="store_true",
        help="Follow log file in real-time (like tail -f)",
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Show full JSON output instead of compact format",
    )

    parser.add_argument("--version", action="version", version="%(prog)s 2.0")

    return parser


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Expand user path and verify log file exists
    log_path = Path(args.logfile).expanduser()
    if not log_path.exists():
        print(f"Error: Log file '{log_path}' not found", file=sys.stderr)
        sys.exit(1)

    try:
        if args.follow:
            print(f"Following {log_path} (Ctrl+C to stop)...")
            tail_file(str(log_path), args.full)
        else:
            read_file(str(log_path), args.full)
    except KeyboardInterrupt:
        print("\nStopped")
    except FileNotFoundError:
        print(f"Error: File '{args.logfile}' not found", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: Permission denied reading '{args.logfile}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
