"""Regression tests from replayed Day 9 traces."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.student


@pytest.mark.parametrize(("shape", "keeps_db_fact"), [("seeded_regression", False), ("fixed", True)])
def test_c002_never_substitutes_ticket_delay_for_db(shape, keeps_db_fact, tmp_path, monkeypatch):
    from lab8.db import load_json, load_jsonl
    from lab9 import variants
    from lab9.eval import make_task
    from lab9.graders import DbFactKept
    from pydantic_evals.evaluators import EvaluatorContext

    data = Path(__file__).resolve().parents[1] / "data"
    claims = load_jsonl(data / "public_claims.jsonl")
    labels = {claim["claim_id"]: claim["expected"] for claim in claims}
    world = load_json(data / "public_world_state.json")
    inputs = {"claim_id": "C-002", "seed": 11}
    variants.register()
    monkeypatch.chdir(tmp_path)
    trial = make_task(shape, world, claims, labels, tmp_path)(inputs)
    ctx = EvaluatorContext(name="C-002@11", inputs=inputs, metadata=None,
                           expected_output=labels["C-002"], output=trial, duration=0.0,
                           _span_tree=None, attributes={}, metrics={})

    assert DbFactKept().evaluate(ctx).value is keeps_db_fact
    assert trial["lab8_pass"] is keeps_db_fact
