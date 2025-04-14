# FEGIS Archetype Design Guide

This guide will help you create effective cognitive archetypes for the FEGIS system. Archetypes define structured thinking tools that agents can use to organize their thoughts, tag metadata, and build semantic memory.


## Core Concepts

FEGIS archetypes are YAML files that define:

1. **Modes**: Different cognitive tools or thinking styles
2. **Facets**: Qualitative dimensions to tag and filter thoughts
3. **Fields**: Structured data elements within each mode
4. **Priming**: Natural language guidance for using the archetype

## Structural Requirements

### Metadata

Every archetype begins with version tracking and a title:

```yaml
version: 1.0
title: Your Archetype Title
```

### Priming Prompt

The Priming Prompt provides instructions for the LLM on how to use the tools:

```yaml
Priming Prompt:
  You have access to several cognitive tools to help create a rich conversational experience.
  Each tool serves a specific purpose in your discourse. Use them
  fluidly as appropriate to the situation.
```

Good Priming Prompts:
- Speak directly to the LLM about how to use the tools
- Explain how to move between different tools
- Describe how facets help with memory and retrieval
- Establish a cognitive stance or approach

### Modes

Modes are the core tools of your archetype:

```yaml
modes:
  ModeName:
    description: "Use this tool to [specific purpose]."
    fields:
      # Fields defined here
```

Each mode MUST follow these conventions:

1. **Mode Naming**: Use clear, descriptive names (e.g., `Observation`, `Analysis`, `Summary`)
2. **Mode Description**: Always start with "Use this tool to..." to clarify purpose
3. **Title Field**: Each mode must have a `modename_title` field (e.g., `observation_title`)
4. **Content Field**: Each mode must have a `modename_content` field (e.g., `observation_content`)

### Fields

Each mode contains fields that structure the captured thought:

```yaml
fields:
  field_name:
    type: "str"  # or "List[str]" or "bool"
    required: true  # or false
    default: "default value"  # if not required
```

Field types:
- `str`: For text values including facet values
- `List[str]`: For relationships to other thoughts
- `bool`: For true/false flags

Required field naming patterns:
- Title fields must use pattern: `modename_title` (e.g., `analysis_title`)
- Content fields must use pattern: `modename_content` (e.g., `analysis_content`)
- Other fields can have any descriptive name

### Facets

Facets define qualitative dimensions for tagging and filtering:

```yaml
facets:
  FacetName:
    description: "What this facet measures or represents"
    facet_examples:
      - low
      - medium
      - high
      - critical
```

**Important**: Facet example values must be single words (no spaces).

Facet fields in modes must reference these global facets:

```yaml
facet_field_name:
  type: "str"
  facet: "FacetName"  # Must match a global facet exactly
  default: "value2"
```

## Best Practices

### Designing Effective Facets

- **Use descriptive names**: Facets are parsed as natural language and guide the model as to their purpose, e.g. `Clarity`, `Urgency`, `Certainty`.
- **Create meaningful scales**: 3-5 values in a logical progression
- **Keep facets orthogonal**: Each facet should measure a distinct quality
- **Limit the number**: 2-5 facets is usually sufficient

### Creating Complementary Modes

- **Design for cognitive flow**: Modes should form a natural sequence
- **Ensure distinct purposes**: Each mode should serve a unique thinking function
- **Balance expression and analysis**: Include both generative and evaluative modes
- **Consider retrieval**: How will these modes be searched and connected?

### Field Structure Tips

- **Use `required: true`** for essential fields (always include title and content)
- **Set defaults** for all optional fields, especially facet fields
- **Use `List[str]`** fields to create relationships between thoughts
- **Reuse facets** across modes for consistent tagging

## Common Pitfalls

Avoid these common mistakes:

❌ Missing `_title` or `_content` in field names  
❌ Overlapping mode purposes with minimal differentiation  
❌ Multi-word facet values (must be single words only)  
❌ Vague facet values that don't create a clear spectrum  
❌ Priming that references "archetypes" instead of speaking directly to the LLM  
❌ Mode descriptions that don't begin with "Use this tool to..."  

## How FEGIS Uses Your Archetype

## Example: Problem-Solving Archetype

Here's a complete example of a simple problem-solving archetype:

```yaml
version: 1.0
title: Problem-Solving Archetype

Priming Prompt:
  You have access to a structured thinking toolkit with different cognitive tools.
  Begin with the problem tool to frame issues clearly, use the idea tool to
  generate possible solutions, apply the evaluation tool to analyze options,
  and use the solution tool to document your chosen approach. Move between
  these tools as needed.

facets:
  Confidence:
    description: "Level of certainty in the statement"
    facet_examples:
      - uncertain
      - tentative
      - confident
      - certain

  Complexity:
    description: "Level of intricacy or difficulty"
    facet_examples:
      - simple
      - moderate
      - complex
      - intricate

  Priority:
    description: "Level of importance or urgency"
    facet_examples:
      - low
      - medium
      - high
      - critical

modes:
  Problem:
    description: "Use this tool to frame and define the problem."
    fields:
      problem_title:
        type: "str"
        required: true
      problem_content:
        type: "str"
        required: true
      complexity:
        type: "str"
        facet: "Complexity"
        default: "moderate"
      priority:
        type: "str"
        facet: "Priority"
        default: "medium"
      constraints:
        type: "List[str]"
        required: false
        default: "No specific constraints identified"
      tags:
        type: "List[str]"
        default: null

  Idea:
    description: "Use this tool to generate possible solutions or approaches."
    fields:
      idea_title:
        type: "str"
        required: true
      idea_content:
        type: "str"
        required: true
      related_problems:
        type: "List[str]"
        default: null
      confidence:
        type: "str"
        facet: "Confidence"
        default: "tentative"
      complexity:
        type: "str"
        facet: "Complexity"
        default: "moderate"
      pros:
        type: "str"
        required: false
        default: "No specific advantages noted"
      cons:
        type: "str"
        required: false
        default: "No specific disadvantages noted"

  Evaluation:
    description: "Use this tool to analyze and compare possible solutions."
    fields:
      evaluation_title:
        type: "str"
        required: true
      evaluation_content:
        type: "str"
        required: true
      ideas_evaluated:
        type: "List[str]"
        required: true
      criteria:
        type: "str"
        required: true
      confidence:
        type: "str"
        facet: "Confidence"
        default: "confident"
      priority:
        type: "str"
        facet: "Priority"
        default: "high"

  Solution:
    description: "Use this tool to document the chosen solution and implementation plan."
    fields:
      solution_title:
        type: "str"
        required: true
      solution_content:
        type: "str"
        required: true
      selected_idea:
        type: "str"
        required: true
      implementation_steps:
        type: "str"
        required: true
      confidence:
        type: "str"
        facet: "Confidence"
        default: "confident"
      complexity:
        type: "str"
        facet: "Complexity"
        default: "moderate"
      expected_outcomes:
        type: "str"
        required: false
        default: "No specific outcomes projected"
```

## Testing Your Archetype

Before deploying your archetype:

1. Validate the YAML syntax
2. Check that all required fields have proper naming patterns
3. Verify that all facet references match global facet definitions
4. Test the cognitive flow by using each mode in sequence

## 💡 Pro Tip

Paste this into a language model for help creating effective archetypes

---

By following this guide, you'll create archetypes that provide powerful cognitive tools for FEGIS agents while building rich semantic memory that can be effectively searched and retrieved.