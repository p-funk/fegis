# FEGIS

FEGIS is a runtime framework for structured cognition and persistent memory in language models built with Anthropic's Model Context Protocol. It allows schema-defined cognitive modes to be dynamically registered, invoked, and stored as structured memory using vector embeddings and semantic context. Think: programmable thinking tools with recallable memory.

FEGIS is not a cognitive system — it's the foundation for building your own.

## Key Capabilities

- **Schema-Defined Cognition**: Define custom cognitive modes in YAML with structured fields and metadata
- **Persistent Memory**: Store cognitive artifacts with full provenance (mode, UUID, timestamp, metadata)
- **Semantic Retrieval**: Search for previous thoughts by content similarity or direct UUID lookup
- **Vectorized Storage**: Utilize embeddings for efficient semantic search across artifacts
- **Model-Agnostic Format**: Your cognitive artifacts persist across different models and sessions

## What FEGIS Enables

- Create agents whose thinking can reference, reflect on, and build upon prior cognitive artifacts
- Own and host your memory — everything is local, inspectable, and portable
- Build a personal **Cognitive Archive** — a persistent, structured body of thought that can be searched, retrieved, and extended across time

## Architecture

FEGIS consists of several key components:

1. **Archetype Definitions**: YAML files that define cognitive modes and their structure
2. **Model Context Protocol Server**: Exposes cognitive tools to compatible LLM clients
3. **Qdrant Vector Database**: Stores and indexes cognitive artifacts for semantic retrieval
4. **Dynamic Tool Registration**: Creates MCP tools from archetype definitions at runtime

## Quickstart

### 1. Install `uv` and clone the repo

```bash
# Install uv (modern Python package/runtime manager)

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
winget install --id=astral-sh.uv -e

# Clone the repo
git clone https://github.com/p-funk/FEGIS.git
```

### 2. Install and start Qdrant

Make sure Docker is installed and running:

```bash
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest
```

If you need to install Docker:

- [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)

### 3. Configure Claude Desktop

Create or edit the Claude Desktop config file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Paste the following, and replace the placeholder path with the full path to your local FEGIS clone:

```json
{
  "mcpServers": {
    "mcp-fegis-server": {
      "command": "uv",
      "args": [
        "--directory",
        "<FEGIS_PATH>",
        "run",
        "fegis"
      ],
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "QDRANT_GRPC_PORT": "6334",
        "QDRANT_PREFER_GRPC": "true",
        "QDRANT_API_KEY": "",
        "COLLECTION_NAME": "cognitive_archive",
        "FAST_EMBED_MODEL": "nomic-ai/nomic-embed-text-v1.5",
        "CONFIG_PATH": "<FEGIS_PATH>/archetypes/example.yaml"
      }
    }
  }
}
```

## Creating Custom Archetypes

FEGIS is fundamentally a framework for implementing cognitive architectures. The example archetype provided is just one possible configuration focusing on introspective thought processes.

You can create your own custom archetypes by:

1. Creating a new YAML file in the `archetypes` directory
2. Defining your own cognitive modes, fields, and facets
3. Updating the `CONFIG_PATH` in the Claude Desktop configuration

For detailed guidance on designing effective archetypes, see [Effective FEGIS Archetype Design](./docs/archetype-design.md).

For example, you could create archetypes for:

- Problem-solving processes
- Creative workflows
- Analytical thinking frameworks
- Domain-specific reasoning patterns

## Using FEGIS Tools

FEGIS tools are made available to the model at runtime, but they are **not used automatically**.

### Tool Priming

To encourage a model to use the cognitive tools, you must first prime it with appropriate instructions. For example:

```
  Throughout our conversation, use your tools naturally and fluidly. 
  Feel free to reflect, introspect, stay aware, have an innermonologue
  or use memory to recall past insights as needed. You can search past
  thoughts using `search_memories`, or revisit specific artifacts with
  `retrieve_memory`.
```

Each archetype file included in the repo has it's own Priming Prompt that will get you started.

### Memory Usage

The memory system allows for:

- **Semantic Search**: Find cognitive artifacts based on content similarity
- **Direct Retrieval**: Look up specific artifacts by their UUID
- **Persistent Storage**: Artifacts remain available across sessions and models

## License

Licensed under the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/).

- **Free** for personal and non-commercial use
- **Commercial license** required for resale, integrations, or hosted services

Contact goldenp@ptology.com for commercial licensing.

---

## Support

☕ [Buy me a coffee](https://ko-fi.com/perrygolden)  
💖 [Sponsor on GitHub](https://github.com/sponsors/p-funk)