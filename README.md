# FEGIS: Structured Memory & Cognitive Framework for LLMs

FEGIS is a Model Context Protocol server that gives LLMs structured, persistent memory through customizable cognitive tools defined in your schema.

## What is FEGIS?

FEGIS transforms how AI models think and remember by creating structured memory tools based on your custom schema. Each memory mode you define becomes a specific thought tool the model can use, with all memories persisting across conversations.

When an LLM uses these memory tools:
- It follows the specific thought structure you've defined
- It considers the qualitative dimensions (facets) you've specified
- The memory persists across all conversations in a vector database
- All memories become searchable through semantic retrieval
- Your memories work across different models and providers

FEGIS doesn't just store information - it structures how AI models organize and retrieve their thoughts.

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

### 3. Configure Your MCP Client

For Claude Desktop, create a configuration file at:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add this JSON configuration:

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
        "CONFIG_PATH": "path/to/your/config.yaml"
      }
    }
  }
}
```

### 4. Create Your Config File

Start simple create a `config.yaml` file to define a basic cognitive framework that will store it's thoughts including their clarity and depth.:

```yaml
facets:
  Clarity:
    description: "How clear or opaque a thought feels"
    facet_examples:  # These examples guide the model directly
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

A more complex sample configuration is available in the `/sample_configs/phenomenology.yaml` file.

A more indepth dive into crafting cognitive memory tools [FEGIS_GUIDE](docs/FEGIS_GUIDE.md)

### 5. Restart Your MCP Client

After configuration, restart your MCP client to load the FEGIS server.

## Why FEGIS Matters

FEGIS offers distinct advantages over other memory approaches:

- **Beyond Simple RAG**: Not just embedding documents - this is structured data with cognitive dimensions
- **Custom Cognitive Frameworks**: Define any memory structure through simple YAML configuration
- **True Persistence**: Data retains its structure and relationships across all sessions
- **Emergent Tool Selection**: Models develop agency in choosing which cognitive tools to use when appropriate
- **Semantic Memory**: Find related memories without exact queries
- **Complete Transparency**: View and manage all memory entries through Qdrant's dashboard interface
- **Privacy-Focused**: No external API calls or cloud dependencies - everything runs on your machine

## Memory Tools

FEGIS has two built-in search tools:

- **search_memories**: Find stored entries by semantic similarity, mode, or metadata
- **retrieve_memory**: Get a specific memory entry by its ID

## Usage Example

Start a conversation with your MCP-enabled client and suggest natural tool usage:

```
Throughout our conversation, use your tools naturally and fluidly as part of your discourse.
Search for and retrieve memories without being explicitly prompted to search_memories when relevant.
Let's discuss artificial intelligence and see how your tools enhance our exploration.
```

## License

This project is licensed under the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/).

- **Free** for personal and non-commercial use
- **Commercial license** required for reselling, integration into paid products, training models on the code, or hosting as a service

Contact goldenp@ptology.com for commercial licensing.

## Support This Project

No upsells, no paywalls—just a guy trying to make the experience of using LLMs better than talking to a knowledgeable goldfish.

☕ [Buy me a coffee](https://ko-fi.com/perrygolden)

💖 [Sponsor on GitHub](https://github.com/sponsors/p-funk)