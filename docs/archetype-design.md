# Effective FEGIS Archetype Design Guide

## Key Structure Requirements

When designing a FEGIS archetype, follow these naming and structural patterns:

1. **Each mode must include a content field.**  This field must follow the naming pattern _content (for example, `thought_content` in the Thought mode)
2. **Each mode must have a title field**.  This field must follow the naming pattern_title that will become the metadata title (for example, `thought_title` in the Thought mode).
    
3. **Fields with a `facet` property** will be stored as qualitative metadata.
    
4. **List fields** will be stored as relationship metadata.
    

---

## Designing Effective Facets

Facets add qualitative dimensions to your cognitive artifacts:

- **Choose Meaningful Qualities:** Select dimensions relevant to your use case.
    
- **Create Intuitive Scales:** Provide examples that form a logical progression.
    
- **Consider Searchability:** Design facets that you might filter by later.
    
- **Balance Complexity:** Include enough facets to be useful without overwhelming.
    

---

## Creating Complementary Modes

Modes are cognitive tools that the model can choose between:

- **Distinct Purposes:** Each mode should serve a unique function.
    
- **Clear Names:** Use descriptive mode names like "Thought", "Introspect", "Reflection", etc.
    
- **Meaningful Descriptions:** Write descriptions that guide when to use each mode.

- **Tool Selection Flow:** Design modes that naturally build on each other.
    

---

## Field Structure Best Practices

Fields define what information each mode captures:
        
- **Required vs. Optional:** Mark essential fields as `required: true`.
    
- **Default Values:** Set sensible defaults for optional fields.
    
- **Relationship Fields:** Use `List[str]` fields to create connections between artifacts.
    

---

## Example: Decision-Making Archetype

```yaml
facets:
  Confidence:
    description: "Level of certainty in information or decision"
    facet_examples:
      - uncertain
      - tentative
      - confident
      - certain

modes:
  Option:
    description: "Use this tool to define a potential choice or alternative"
    fields:
      option_title:  # Required title field pattern
        type: "str"
        required: true
      option_content:  # Content field (follows naming convention)
        type: "str"
        required: true
      confidence:  # Facet field
        type: "str"
        facet: "Confidence"
        default: "tentative"
      pros:  # Relationship field
        type: "List[str]"
        default: null
      cons:  # Relationship field
        type: "List[str]"
        default: null

  Decision:
    description: "Use this tool to record final choices and rationales"
    fields:
      decision_title:  # Required title field pattern
        type: "str"
        required: true
      decision_content:  # Content field (follows naming convention)
        type: "str"
        required: true
      confidence:
        type: "str"
        facet: "Confidence"
        required: true
      selected_options:  # Relationship field for linking to options
        type: "List[str]"
        default: null
```

---

## Testing Your Archetype

1. **Start Conversations:** Use your new archetype in real conversations.
    
2. **Mode Selection:** Observe how the model selects between different modes.
    
3. **Facet Evaluation:** Check if the facets provide meaningful distinctions.
    
4. **Relationship Functionality:** Test the search and relationship functionality.
    
5. **Iterative Refinement:** Refine based on actual usage patterns.
    

---

## Common Patterns & Anti-Patterns

**Effective Patterns:**

- Modes that form natural thinking sequences.
    
- Facets with clear, intuitive progressions.
    
- Relationship fields that create meaningful connections.
    
- Clear, guiding descriptions for each mode.
    

**Anti-Patterns to Avoid:**

- Omitting the required naming patterns (for title and content fields).
    
- Modes with overlapping purposes.
    
- Too many facets that overwhelm decision-making.
    
- Inadequate relationship fields to connect related thoughts.
    

