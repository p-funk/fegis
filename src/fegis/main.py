import argparse


def main():
    """
    Fegis Entry Point - Declarative Interaction Compiler

    Initializes the Fegis server with appropriate transport protocol and loads:

    1. Archetype Definition: YAML-based specification of:
       - Semantic parameters (dimensions like Clarity, Depth)
       - Tool interfaces (structured interaction patterns)
       - Frame schemas (validation rules for outputs)

    2. Trace Archive: Vector-based persistent memory system that:
       - Automatically embeds and stores all tool invocations
       - Enables semantic search by similarity
       - Supports filtering by parameter values and frame content
       - Maintains chronological context through timestamps

    The server exposes each tool defined in the archetype, automatically generating
    handlers that validate inputs, persist outputs, and return trace references.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Fegis: A schema-driven interaction compiler for structured tool execution and persistent semantic memory"
    )

    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol to use. 'stdio' for standard I/O, 'sse' for Server-Sent Events"
    )

    args = parser.parse_args()

    from fegis.server import mcp

    # Run the server with the configured transport
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
