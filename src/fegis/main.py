import argparse


def main():
    """
    Main entry point for FEGIS.

    Parses command-line arguments and starts the FEGIS server with the
    appropriate transport.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="FEGIS: A schema-driven cognitive framework that gives LLMs structured tools and persistent cognitive artifacts"
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
