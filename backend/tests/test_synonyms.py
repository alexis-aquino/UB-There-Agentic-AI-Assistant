from app.brain.synonyms import _STEMMED, flatten, query_concepts
from app.brain.text import stem


def test_phrase_rewrite_drops_filler_word():
    concepts = query_concepts("What is the dress code?")
    heads = [concept[0] for concept in concepts]
    assert stem("code") not in heads
    assert concepts[0] == [stem("dress"), stem("uniform"), stem("attire")]


def test_handbook_wording_is_not_expanded():
    assert query_concepts("school uniform policy") == [
        [stem("school")],
        [stem("uniform")],
        [stem("policy")],
    ]


def test_repeated_terms_collapse_to_one_concept():
    assert len(query_concepts("uniform uniform")) == 1


def test_flatten_keeps_order_without_duplicates():
    assert flatten([["a", "b"], ["b", "c"]]) == ["a", "b", "c"]


def test_every_synonym_target_exists_in_the_documents(index):
    """A target the corpus never uses silently does nothing — catch it when editing."""
    missing = sorted(
        {target for targets in _STEMMED.values() for target in targets} - set(index.postings)
    )
    assert not missing, f"Synonym targets not in the index: {missing}"
