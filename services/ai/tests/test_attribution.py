from fixtures import evidence

from tibyan_ai.pipeline.attribution import Match, coverage, decide, is_verbatim, split_claim
from tibyan_ai.text.arabic import tokens

BAZ = "إذا عزم المسافر على الإقامة أكثر من أربعة أيام أتم الصلاة، وإن كانت أربعة أيام فأقل قصر."
CLAIM = "إذا عزم المسافر على الإقامة أكثر من أربعة أيام أتم الصلاة"


def match(slug: str, passage: str, claim: str = CLAIM) -> Match:
    c = evidence()
    c.source = {**c.source, "slug": slug}
    return Match(c, passage, coverage(tokens(claim), tokens(passage)))


def judge_says(label: str):
    return lambda items: {i: (label, "judge") for i, _p, _h in items}


def test_a_forwarded_message_is_split_into_the_statement_and_the_scholar_named():
    text = "قال سماحة الشيخ ابن باز رحمه الله: «إذا عزم المسافر على الإقامة أكثر من أربعة أيام أتم» اهـ"
    claim, named = split_claim(text)
    assert claim == "إذا عزم المسافر على الإقامة أكثر من أربعة أيام أتم" and named == "binbaz"
    assert split_claim("يقول الشيخ العثيمين: الصلاة في الطائرة صحيحة إذا لم يتمكن")[1] == "binothaimeen"
    assert split_claim("إذا عزم المسافر على الإقامة أتم الصلاة")[1] is None


def test_a_negated_sentence_is_never_reported_as_verbatim():
    assert is_verbatim(tokens("يجوز تأخير الصلاة"), tokens("قال: يجوز تأخير الصلاة للعذر"))
    assert not is_verbatim(tokens("يجوز تأخير الصلاة"), tokens("لا يجوز تأخير الصلاة عن وقتها"))


def test_word_for_word_statement_of_the_named_scholar_is_verbatim_without_asking_the_judge():
    def judge(items):
        raise AssertionError("the judge is only for statements that are not word for word")

    verdict, m, _ = decide(CLAIM, [match("binbaz", BAZ)], "binbaz", judge)
    assert verdict == "verbatim" and m.slug == "binbaz"


def test_altered_statement_is_judged_for_meaning():
    altered = "إذا عزم المسافر على الإقامة أكثر من خمسة عشر يوما أتم الصلاة"
    m = [match("binbaz", BAZ, altered)]
    assert decide(altered, m, "binbaz", judge_says("contradicted"))[0] == "contradicted"
    assert decide(altered, m, "binbaz", judge_says("entailed"))[0] == "meaning"
    assert decide(altered, m, "binbaz", None)[0] == "similar"  # no judge configured: wording only


def test_statement_found_only_in_another_scholars_fatwa_is_misattributed():
    verdict, m, _ = decide(CLAIM, [match("binothaimeen", BAZ)], "binbaz", judge_says("neutral"))
    assert verdict == "misattributed" and m.slug == "binothaimeen"


def test_nothing_close_is_not_found():
    unrelated = match("binbaz", "الزكاة واجبة في الذهب إذا بلغ النصاب وحال عليه الحول.")
    assert decide(CLAIM, [unrelated], "binbaz", judge_says("entailed")) == ("not_found", None, None)
    assert decide(CLAIM, [], None, None)[0] == "not_found"
