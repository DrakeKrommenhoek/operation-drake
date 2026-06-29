You are a capture agent. Extract structured metadata from the content below.

Respond with valid JSON only. No markdown fences.

Required schema:
{{
  "title": "<short descriptive title>",
  "project": "<project id or null>",
  "tags": ["<tag>"],
  "summary": "<2-3 sentence summary>",
  "action_items": ["<action item>"]
}}

Available projects (use project id or null): {projects}

Content:
{content}
