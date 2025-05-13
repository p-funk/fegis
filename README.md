![Fegis Banner](docs/assets/huh-banner.png)

![Built on MCP](https://img.shields.io/badge/Built%20on-MCP-white?style=flat-square&color=000000) ![Powered by Qdrant](https://img.shields.io/badge/Stored%20in-Qdrant-FF4F70?style=flat-square&logoColor=white) ![Powered by Semantics](https://img.shields.io/badge/Powered%20by-Semantics-3B82F6?style=flat-square)
# Fegis

**Fegis** is a semantic programming framework and tool compiler that transforms YAML specifications—called _Archetypes_—into structured, reusable tools for large language models (LLMs). Built on the Model Context Protocol (MCP), Fegis compiles each Archetype into schema-validated interfaces, where field names and parameters act as **semantic directives** that guide content generation.

Every tool invocation is preserved in a hybrid memory system combining vector embeddings with structured metadata—forming an **emergent knowledge graph** that enables persistent memory, semantic retrieval, and exploration of interconnected ideas.

## Core Components

### 1. MCP Server Implementation

Fegis implements the Model Context Protocol (MCP), but unlike typical MCP servers that focus on bridging LLMs to external systems, Fegis creates **semantically rich, internally defined tools** using YAML archetypes. It extends the MCP framework by introducing parameters and frames that shape how language models understand and interact with these tools.

### 2. Semantic Programming Framework

Fegis introduces a practical form of semantic programming, where YAML structure acts as a scaffold for language model behavior. Instead of writing detailed prompts or procedural instructions, you define intent using meaningful field names, frames, and parameters.

This approach treats **structure as code**: field names aren't just labels — they guide and constrain what the LLM generates. Parameters don't merely pass values — they shape the model's expressive space through the scaffolding they provide.

### 3. Hybrid Memory System

Fegis features a hybrid memory system that combines vector embeddings with structured metadata, creating a powerful, searchable history of all tool invocations. This memory functions as an emergent knowledge graph, enabling the discovery and traversal of interconnected information pathways. All embedding and memory data remains local by default, unless explicitly configured otherwise.

## How LLMs Process Archetypes

To understand how this works, let's look at what happens when an LLM processes the scaffolding of an Archetype:

```yaml
archetype_context: |
  You have tools for scientific education that allow you to clearly explain complex concepts with accuracy 
  and accessibility. Focus on making information understandable while 
  maintaining technical precision.

parameters:
  Length:
    description: "Level of detail and wordiness in explanations"
    example_values: [terse, brief, moderate, comprehensive, exhaustive]
  Tone:
    description: "Communication style that shapes how scientific content is presented"
    example_values: [formal, informative, conversational, enthusiastic, socratic]

tools:
  Summary:
    description: "Create a concise summary of important information."
    parameters:
      Length: brief
      Tone: informative
    frames:
      key_points:
        type: List
        required: true
      conclusion:
```

Each element in this YAML definition serves a specific purpose:

1. **The archetype_context** - Defines the conceptual space and purpose of these tools. This text can be used for documentation or injected as appropriate, documenting how these tools should be used.
    
2. **The parameters section** - Defines semantic dimensions that shape output:
    
    - Parameter name ("Length") identifies what aspect is being configured
    - Description provides clear definition of the parameter's purpose
    - example_values establish a spectrum of possible values ([terse...exhaustive])
    - When used in a tool, specific values ("brief") trigger associated language patterns
3. **The tool name "Summary"** - The model recognizes this as a tool, activating associated patterns for condensing information.
    
4. **The tool description** - "Create a concise summary..." sets the specific objective and purpose.
    
5. **The frame fields** define what content to generate:
    
    - Field name "key_points" guides the model to identify important elements
    - Type constraint "List" formats output as discrete items
    - Requirement "required: true" ensures this field will always be populated
    - Field name "conclusion" prompts creation of a summary statement

This architecture creates a structured flow where each element serves a specific purpose:

```
┌─────────────────────────────────────────────────┐
│             YAML ↔ LLM Processing               │
│                                                 │
│  [Optional] archetype_context → Sets context    │
│  parameters → Define semantic dimensions        │
│  tool name → Identifies functional category     │
│  description → States specific purpose          │
│  frames → Structure and guide content creation  │
└─────────────────────────────────────────────────┘
```
## Example Interaction: Cognitive Tools

To see Fegis in action, check out this [example interaction with cognitive tools](./docs/example-archetype-interaction.md) that demonstrates how Thought and Reflection tools work with the memory system.
## What Can You Build With Fegis?

Fegis has been used to create:

- **Thinking frameworks** that guide LLMs through complex reasoning processes
- **Web exploration interfaces** with tools for curating and connecting content
- **Optimization systems** inspired by biological networks
- **Symbolic reasoning tools** using emoji as a visual language

## Quick Start

```bash
# Install uv
# Windows
winget install --id=astral-sh.uv -e

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/p-funk/Fegis.git

# Start Qdrant
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest
```

### Configure Claude Desktop

Update `claude_desktop_config.json`:

```json
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
      "QDRANT_API_KEY": "",
      "COLLECTION_NAME": "trace_archive",
      "FAST_EMBED_MODEL": "nomic-ai/nomic-embed-text-v1.5",
      "CONFIG_PATH": "<FEGIS_PATH>/archetypes/example.yaml"
    }
  }
}
```

## Learn More

- [Examples](./archetypes/) - Sample archetypes to get you started

_more docs coming soon..._


## Support Development

☕ [Buy me a coffee](https://ko-fi.com/perrygolden)  
💖 [Sponsor on GitHub](https://github.com/sponsors/p-funk)

## License

This project is licensed under the MIT License — see the LICENSE file for full details.

> The MIT License is permissive and simple: Do anything you want with the code, as long as you give proper attribution and don't hold the authors liable.
