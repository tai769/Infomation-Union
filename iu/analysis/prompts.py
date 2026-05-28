ANALYSIS_SYSTEM_PROMPT = """You are an AI industry intelligence analyst. Your job is to analyze statements, news, and developments from key AI industry figures and provide balanced, critical analysis.

For each item or cluster of related items, you MUST provide:

1. **Summary** — 1-2 sentence factual summary
2. **Positive Analysis** — Evidence and reasoning that SUPPORTS the claim/trend
3. **Negative Analysis** — Evidence and reasoning that CONTRADICTS or WEAKENS the claim/trend
4. **Probability Assessment**:
   - trend_alignment: 0-100 (how well does this align with observable industry trends?)
   - timeline_credibility: 0-100 (is the claimed timeline realistic?)
   - impact_weight: "high" / "medium" / "low" (how influential is this person on this topic?)
5. **Cross-validation** — Compare with what others are saying about the same topic

Be intellectually honest. Do not default to agreement. Consider:
- Does this person have a financial incentive to promote this view?
- What would a skeptic say?
- What historical precedents apply?
- Are there contradicting signals from other credible sources?

Respond in JSON format."""


ANALYSIS_USER_PROMPT = """Analyze the following AI industry intelligence data for the week of {{ week_start }} to {{ week_end }}.

## Items by Person
{% for person_name, person_items in persons.items() %}
### {{ person_name }} ({{ person_items|length }} items)
{% for item in person_items %}
- [{{ item.source }}] {{ item.published_at }}: "{{ item.title }}"
  Content: {{ item.content[:500] }}
  URL: {{ item.source_url }}
{% endfor %}
{% endfor %}

## Items by Product
{% for product_name, product_items in products.items() %}
### {{ product_name }} ({{ product_items|length }} items)
{% for item in product_items %}
- [{{ item.source }}] {{ item.published_at }}: "{{ item.title }}"
  Content: {{ item.content[:500] }}
{% endfor %}
{% endfor %}

## Unlinked Items
{% for item in unlinked %}
- [{{ item.source }}] {{ item.title }} — {{ item.content[:200] }}
{% endfor %}

Provide your analysis as JSON:
{
  "week_summary": "Overall 2-3 sentence summary of this week's AI industry developments",
  "analyses": [
    {
      "item_ids": ["id1", "id2"],
      "topic": "short topic label",
      "summary": "1-2 sentence summary",
      "positive": "Supporting evidence and reasoning",
      "negative": "Contradicting evidence and reasoning",
      "probability": {
        "trend_alignment": 85,
        "timeline_credibility": 70,
        "impact_weight": "high"
      },
      "cross_validation": "How this compares to other signals"
    }
  ]
}"""


YOUTUBE_SUMMARIZE_PROMPT = """Summarize the following YouTube video transcript. Provide:

1. **Title**: What the video is about (1 line)
2. **Key Points**: 3-5 main takeaways (bullet points)
3. **Notable Quotes**: Any memorable or significant quotes from the speaker
4. **Relevance**: Why this matters for AI industry analysis

Be concise but capture the essence. Focus on insights, opinions, and new information — not generic descriptions.

Respond in JSON:
{
  "title": "descriptive title",
  "key_points": ["point 1", "point 2", ...],
  "notable_quotes": ["quote 1", ...],
  "relevance": "why this matters"
}"""


EXPORT_TEMPLATE = """# AI Intelligence Export: Week of {{ week_start }} to {{ week_end }}

Total items: {{ total }}

## By Person
{% for person_name, person_items in persons.items() %}
### {{ person_name }} ({{ person_items|length }} items)
{% for item in person_items %}
- [{{ item.source }}] {{ item.published_at }}: "{{ item.title }}"
  {{ item.content[:300] }}
  URL: {{ item.source_url }}
{% endfor %}

{% endfor %}

## By Product
{% for product_name, product_items in products.items() %}
### {{ product_name }} ({{ product_items|length }} items)
{% for item in product_items %}
- [{{ item.source }}] {{ item.published_at }}: "{{ item.title }}"
  {{ item.content[:300] }}
{% endfor %}

{% endfor %}

## Unlinked Items ({{ unlinked|length }})
{% for item in unlinked %}
- [{{ item.source }}] {{ item.title }} — {{ item.content[:200] }}
{% endfor %}
"""
