from __future__ import annotations

from llm_wiki.llm.chat import extract_json_object


def test_extract_json_object_repairs_unescaped_quotes_inside_value_strings() -> None:
    raw = '''```json
{
  "task_type": "extract_claims",
  "claim_candidates": [
    {
      "candidate_key": "claim_01",
      "statement": "Claude Code sends "tool schemas": before prompt and this should stay inside the claim.",
      "review_reason": "The quote includes "special": markers from source text."
    }
  ],
  "node_candidates": []
}
```'''

    parsed = extract_json_object(raw)

    claim = parsed["claim_candidates"][0]
    assert claim["statement"] == 'Claude Code sends "tool schemas": before prompt and this should stay inside the claim.'
    assert claim["review_reason"] == 'The quote includes "special": markers from source text.'


def test_extract_json_object_repairs_missing_commas_between_properties() -> None:
    raw = '''{
      "task_type": "extract_claims"
      "source_id": "source_abc",
      "schema_version": "candidate.v1",
      "claim_candidates": []
      "node_candidates": []
    }'''

    parsed = extract_json_object(raw)

    assert parsed["task_type"] == "extract_claims"
    assert parsed["source_id"] == "source_abc"
    assert parsed["claim_candidates"] == []
    assert parsed["node_candidates"] == []
