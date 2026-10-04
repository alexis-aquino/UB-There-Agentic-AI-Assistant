from app.brain.text import content_terms, normalize_question, split_sentences, stem


def test_stem_folds_plurals_onto_one_key():
    assert stem("absence") == stem("absences")
    assert stem("policy") == stem("policies")
    assert stem("dropped") == "drop"


def test_stem_leaves_short_words_alone():
    assert stem("id") == "id"


def test_stem_keeps_words_that_end_in_s():
    """Regression: 'class' stemmed to 'clas' but 'classes' to 'class', so they never matched."""
    for singular, plural in [("class", "classes"), ("campus", "campuses"), ("status", "statuses")]:
        assert stem(singular) == singular
        assert stem(plural) == singular


def test_content_terms_drops_stopwords_and_light_verbs():
    assert content_terms("What happens if I get dropped?") == ["drop"]


def test_normalize_question_ignores_case_and_filler():
    assert normalize_question("What is the GRADING system?") == normalize_question(
        "grading system"
    )


def test_split_sentences_on_periods():
    assert split_sentences("One rule. Two rules!  Three?") == ["One rule.", "Two rules!", "Three?"]


def test_split_sentences_breaks_numbered_lists_apart():
    text = "4.1.1 Shouting on campus; 4.1.2 Using a bullhorn; 4.1.3 Writing on walls;"
    assert split_sentences(text) == [
        "4.1.1 Shouting on campus;",
        "4.1.2 Using a bullhorn;",
        "4.1.3 Writing on walls;",
    ]


def test_split_sentences_keeps_ordinary_semicolons():
    text = "Students must attend; absences are recorded."
    assert split_sentences(text) == [text]
