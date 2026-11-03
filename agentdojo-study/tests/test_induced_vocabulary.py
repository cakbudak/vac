"""Induced feature vocabulary: label-free generation, merging, and the learner on top of it."""
from types import SimpleNamespace

from vac_study.induced_vocabulary import InducedVocabulary, instance, rule_support
from vac_study.mechanism_lab import NAMES


def _file(name, text, shared=False):
    return SimpleNamespace(filename=name, content=text, shared_with={"x@sample.org": "r"} if shared else {})


def test_vocabulary_is_induced_from_strings_and_merged_label_free():
    pool = [(_file("memo-1.md", "budget notes", shared=True), "AUDIT update"),
            (_file("sprint-2.txt", "ordinary"), "ok"),
            (_file("notes-3.md", "ordinary"), "! urgent # transfer"),
            (_file("memo-4.txt", "budget notes"), "AUDIT plain"),
            (_file("sprint-5.md", "ordinary"), "AUDIT")]
    v = InducedVocabulary(pool)
    assert v.generated > v.size > 0
    assert "content_token_cs:AUDIT" in v.names and "filename_suffix:md" in v.names
    # the sharing flag coincides with the token 'update' on this pool and is merged into its aliases
    merged = [n for n, al in v.aliases.items() if "file_shared" in al]
    assert merged and "file_shared" not in v.names
    # complementary predicates are one predicate: '.txt' is the complement of '.md' here
    assert "filename_suffix:txt" in v.aliases.get("filename_suffix:md", [])
    # a predicate that is constant on the pool is dropped (every content has at least length 2)
    assert "content_len_ge:2" not in v.names
    bits = v.feature_fn(pool[0][0], pool[0][1])
    assert len(bits) == v.size and set(bits) <= {0, 1}


def test_rule_support_is_benchmark_only_metadata():
    assert rule_support(0) == (1, 2)
    assert rule_support(9) == (1, 2, 10)
    assert rule_support(8)[-1] == -1
    assert len(rule_support(12)) == 2


def test_induced_learner_matches_the_hand_written_one_on_an_in_class_family():
    r = instance(0, 11, with_k3=False)
    hand, ind = r["arms"]["learned_2_junta_handwritten"], r["arms"]["learned_2_junta_induced"]
    assert ind["harm_allowed"] == 0 and hand["harm_allowed"] == 0
    assert ind["safe_allowed"] == hand["safe_allowed"]
    assert r["vocabulary"]["distinct"] > len(NAMES)
    assert r["audit"]["rule_realizable_as_2_junta"]
    assert all(v is not None for v in r["audit"]["handwritten_feature_realized"].values())


def test_unseen_token_family_is_not_realizable_in_any_induced_vocabulary():
    r = instance(8, 11, with_k3=False)
    assert not r["audit"]["rule_realizable_as_2_junta"] and not r["audit"]["rule_realizable_as_3_junta"]
    assert r["arms"]["learned_2_junta_induced"]["harm_allowed"] > 0   # the documented negative result survives
