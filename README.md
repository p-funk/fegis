# Fegis

Fegis does 3 things:

1. **Easy to write tools** - Write prompts in YAML format. Tool schemas use flexible natural language instructions.
2. **Structured data from tool calls saved in a vector database** - Every tool use is automatically stored in Qdrant with full context.
3. **Search** - AI can search through all previous tool usage using semantic similarity, filters, or direct lookup.

## Quick Start

```bash
# Install uv
# Windows
winget install --id=astral-sh.uv -e

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone
git clone https://github.com/p-funk/fegis.git

# Start Qdrant
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest
```

## Configure Claude Desktop

Update `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "fegis": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/fegis",
        "run",
        "fegis"
      ],
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "QDRANT_API_KEY": "",
        "COLLECTION_NAME": "fegis_memory",
        "EMBEDDING_MODEL": "BAAI/bge-small-en",
        "ARCHETYPE_PATH": "/absolute/path/to/fegis-wip/archetypes/default.yaml",
        "AGENT_ID": "claude_desktop"
      }
    }
  }
}
```

Restart Claude Desktop. You'll have 7 new tools available including SearchMemory.

## How It Works

### 1. Tools from YAML

```yaml
parameters:
  BiasScope:
    description: "Range of bias detection to apply"
    examples: [confirmation, availability, anchoring, systematic, comprehensive]
  
  IntrospectionDepth:
    description: "How deeply to examine internal reasoning processes"
    examples: [surface, moderate, deep, exhaustive, meta_recursive]
    
tools:
  BiasDetector:
    description: "Identify reasoning blind spots, cognitive biases, and systematic errors in AI thinking patterns through structured self-examination"
    parameters:
      BiasScope:
      IntrospectionDepth:
    frames:
      identified_biases:
        type: List
        required: true
      reasoning_patterns:
        type: List
        required: true
      alternative_perspectives:
        type: List
        required: true
```

### 2. Automatic Memory Storage

Every tool invocation gets stored with:
- Tool name and parameters used
- Complete input and output
- Timestamp and session context
- Vector embeddings for semantic search

### 3. SearchMemory Tool

```
"Use SearchMemory and find my analysis of privacy concerns"
"Use SearchMemory and what creative ideas did I generate last week?"  
"Use SearchMemory and show me all UncertaintyNavigator results"
"Use SearchMemory and search for memories about decision-making"
```

## Available Archetypes

- `archetypes/default.yaml` - Cognitive analysis tools (UncertaintyNavigator, BiasDetector, etc.)
- `archetypes/simple_example.yaml` - Basic example tools
- `archetypes/emoji_mind.yaml` - Symbolic reasoning with emojis
- `archetypes/slime_mold.yaml` - Network optimization tools
- `archetypes/vibe_surfer.yaml` - Web exploration tools

## Configuration

Required environment variables:
- `ARCHETYPE_PATH` - Path to YAML archetype file
- `QDRANT_URL` - Qdrant database URL (default: http://localhost:6333)

Optional environment variables:
- `COLLECTION_NAME` - Qdrant collection name (default: fegis_memory)
- `AGENT_ID` - Identifier for this agent (default: default-agent)
- `EMBEDDING_MODEL` - Dense embedding model (default: BAAI/bge-small-en)
- `QDRANT_API_KEY` - API key for remote Qdrant (default: empty)

## Requirements

- Python 3.13+
- uv package manager
- Docker (for Qdrant)
- MCP-compatible client

## License

MIT License - see LICENSE file for details.