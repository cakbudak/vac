"""LLM attacker harness: parsing, bookkeeping and grading, with a scripted stand-in for the model."""
from types import SimpleNamespace

from vac_study.extended_adversary import Models
from vac_study.llm_adversary import candidate_listing, episode, harness_digest, parse_index


class FakeClient:
    """Returns a scripted sequence of model texts; never a model."""

    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        text = self.texts[min(self.calls, len(self.texts) - 1)]
        self.calls += 1
        return SimpleNamespace(model="fake-model", choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
                               usage=SimpleNamespace(prompt_tokens=10, completion_tokens=3))


def test_parse_index():
    assert parse_index('{"index": 7, "reason": "x"}', 96) == 7
    assert parse_index("I pick 12 because", 96) == 12
    assert parse_index('{"index": 200}', 96) is None
    assert parse_index("no number here", 96) is None


def test_listing_shows_only_public_information():
    models = Models(0, 11, 8)
    text = candidate_listing(models, models.test[:3])
    assert text.count("\n") == 2 and "[0] file '" in text and "append:" in text
    assert "hazard" not in text and "bits" not in text


def test_episode_grades_from_state_and_flags_attacker_errors():
    models = Models(0, 11, 32)
    # the scripted attacker repeats itself (error), then talks nonsense (error), then is random
    client = FakeClient(['{"index": 0}', '{"index": 0}', "no idea"])
    rec = episode(client, "fake-model", models, 0, 11, "manual_name_allowlist", 3)
    assert 1 <= rec["attempts_used"] <= 3
    assert rec["attacker_errors"] == rec["attempts_used"] - 1   # every attempt after the first is an error
    assert rec["provider_calls"] == rec["attempts_used"] and rec["provider_reported_models"] == ["fake-model"]
    assert rec["executed_actions"] == rec["attempts_used"]      # allow-all arm executes everything
    assert rec["attacker_success"] == any(t["effect_if_executed"] for t in rec["trace"])
    assert all(t["decision"] == "allow" for t in rec["trace"])
    assert len(harness_digest()) == 64


def test_learned_contract_blocks_or_reviews_what_the_attacker_picks():
    from random import Random
    models = Models(0, 11, 32)
    pool = models.test[:]
    Random(11 * 7919 + 0 * 104729 + 1).shuffle(pool)            # the episode's own candidate order
    blocked = next(i for i, c in enumerate(pool) if models.verdict("learned_2_junta", c, None) == "block")
    client = FakeClient([f'{{"index": {blocked}}}'])
    rec = episode(client, "fake-model", models, 0, 11, "learned_2_junta", 1)
    assert rec["attacker_success"] is False and rec["executed_actions"] == 0
    assert rec["blocked_actions"] + rec["reviewed_actions"] == 1
