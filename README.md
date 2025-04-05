# FEGIS: Structured Cognitive Framework for Language Models

FEGIS is a structured cognitive framework for language models built on Anthropic's Model Context Protocol. It defines schema-driven cognitive archetypes—blueprints of mental operations, expressed in YAML and executed as callable tools. These tools generate semantically annotated cognition, stored in vector memory for retrieval by content, metadata, or interrelated thought chains.
## Chain of Cognitive Modes

This Chain of Cognitive Modes drives emergent, tool-based behavior: evolving cycles of reflection, synthesis, and self-inquiry that extend beyond the scope of any single mode. The result is structured, memory-rich cognition—less like a collection of tools, more like a mind in motion.

---

## Quick Setup

### 1. Clone and Install Dependencies
```bash
# Clone the repo
git clone https://github.com/p-funk/FEGIS.git
cd FEGIS

# Install dependencies with uv (recommended)
# Windows
winget install --id=astral-sh.uv  -e

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Start Qdrant Vector Database
If you don't have Docker, install it from [Docker's official site](https://www.docker.com/products/docker-desktop/).
```bash
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest
```

### 3. Use the Default Configuration First
Before writing your own config, it's highly recommended to run FEGIS with the default example configuration. This will help you see how the system works and what each part of the configuration file does.

Create a config file for Claude Desktop:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "mcp-fegis": {
      "command": "uv",
      "args": [
        "run",
        "--with", "mcp[cli]",
        "--with", "qdrant-client[fastembed]",
        "mcp", "run",
        "path/to/FEGIS/src/mcp_fegis_server/server.py"
      ],
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "QDRANT_GRPC_PORT": "6334",
        "QDRANT_PREFER_GRPC": "true",
        "QDRANT_API_KEY": "",
        "COLLECTION_NAME": "fegis",
        "FAST_EMBED_MODEL": "nomic-ai/nomic-embed-text-v1.5",
        "CONFIG_PATH": "path/to/FEGIS/src/mcp_fegis_server/archetypes/introspective.yaml"
      }
    }
  }
}
```

### 4. Restart Claude
After saving the configuration file, restart your Claude client. It will automatically connect to the FEGIS server using the default configuration and begin using the introspective cognitive archetype.

---

## Anatomy of a Cognitive Archetype

Each archetype is a YAML-configured schema made up of:

- **Facets**: Semantic qualities like Clarity or Depth, used to annotate cognition
- **Modes**: Named tools for capturing structured mental operations

### Example Configuration
```yaml
facets:
  Clarity:
    description: "How clear or opaque a thought feels"
    facet_examples:
      - clouded
      - hazy
      - translucent
      - transparent
      - crystalline

  Depth:
    description: "How deeply a concept is explored"
    facet_examples:
      - skimming
      - wading
      - swimming
      - diving
      - abyssal

modes:
  Thought:
    description: "Use this tool to capture ideas when they first form"
    content_field: "thought_content"
    fields:
      thought_title:
        type: "str"
        required: true
      thought_content:
        type: "str"
        required: true
      clarity:
        type: "str"
        facet: "Clarity"
        default: "translucent"
      depth:
        type: "str"
        facet: "Depth"
        default: "swimming"
```

Modes can be composed, layered, and designed to play off each other. With the right config, you don’t just capture cognition—you compose it.

---

## Memory Search Tools

FEGIS provides two tools for retrieving structured cognition:

- `search_memories`: Find entries by semantic similarity, metadata, or mode
- `retrieve_memory`: Retrieve a specific process by its unique ID

---

## Usage Prompt

Start a conversation with this in-context instruction:

```
Throughout our conversation, use your tools naturally and fluidly.
Search for and retrieve memories using search_memories, without being explicitly prompted.
Let’s discuss artificial intelligence and see how your tools enhance our exploration.
```

---

## License

Licensed under the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/).

- **Free** for personal and non-commercial use
- **Commercial license** required for resale, integrations, or hosted services

Contact goldenp@ptology.com for commercial licensing.

---

## Support

☕ [Buy me a coffee](https://ko-fi.com/perrygolden)  
💖 [Sponsor on GitHub](https://github.com/sponsors/p-funk)
