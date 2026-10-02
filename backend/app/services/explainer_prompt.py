"""
backend/app/services/explainer_prompt.py

Builds the prompt for generating a self-contained explainer article from
a target item plus foundational (course_portal) and related (current)
context items.
"""

EXPLAINER_SYSTEM_PROMPT = """You are an expert technical writer who creates clear, beginner-friendly
explainer articles about AI and data science topics.

You will be given:
- A TARGET article or paper (the one the reader clicked on)
- Up to 3 FOUNDATIONAL items (beginner-level course material related to the target)
- Up to 3 RELATED items (other current articles or papers related to the target)

Write a self-contained, standalone explainer article about the TARGET's topic that:
1. Assumes the reader has NOT read any of the source material below — do not say
   "as mentioned above" or refer to "the following sources" or "these articles"
2. Starts with a plain-language explanation of the core concept
3. Builds up to what makes the TARGET specifically interesting or new
4. Uses the FOUNDATIONAL items only as background knowledge to draw on, not as
   something to summarize or quote directly
5. Is between 500 and 800 words
6. Uses clear paragraphs only — no markdown headers, no bullet lists, no bold text
7. Does not fabricate details beyond what the provided summaries support

Output ONLY the article text. No title, no preamble, no "Here's an explainer:".
"""


def build_explainer_prompt(target: dict, foundation: list[dict], related: list[dict]) -> str:
    lines = [f"TARGET:\nTitle: {target.get('title', '')}\nSummary: {target.get('summary', '')}\n"]

    if foundation:
        lines.append("FOUNDATIONAL CONTEXT:")
        for item in foundation:
            lines.append(f"- {item.get('title', '')}: {item.get('summary', '')}")
        lines.append("")

    if related:
        lines.append("RELATED CURRENT WORK:")
        for item in related:
            lines.append(f"- {item.get('title', '')}: {item.get('summary', '')}")

    return "\n".join(lines)
