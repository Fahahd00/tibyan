from tibyan_ai.ingestion.binbaz import content_hash
from tibyan_ai.ingestion.hadeethenc import snapshot

ITEM = {  # shape of https://hadeethenc.com/api/v1/hadeeths/one/?language=ar&id=2962 (abridged)
    "id": "2962",
    "title": "أول ما يقضى بين الناس يوم القيامة في الدماء",
    "hadeeth": "عن عبد الله بن مسعود رضي الله عنه قال: قال رسول الله ﷺ: «أول ما يقضى بين الناس يوم القيامة في الدماء».",
    "attribution": "متفق عليه",
    "grade": "صحيح",
    "explanation": "ذكر النبي ﷺ أن أول ما يحكم فيه بين الناس يوم القيامة الدماء.",
    "hints": ["عظم أمر الدماء.", " "],
    "reference": "صحيح البخاري (6864).",
}


def test_a_hadith_is_stored_with_its_grade_explanation_and_benefits_verbatim():
    snap = snapshot(ITEM, "الفقه وأصوله")
    assert snap.source_slug == "hadeethenc" and snap.external_id == "2962"
    assert snap.url == "https://hadeethenc.com/ar/browse/hadith/2962"
    paragraphs = snap.answer.split("\n\n")
    assert paragraphs[0] == f"{ITEM['hadeeth']} [صحيح — متفق عليه]"  # the hadith itself first
    assert paragraphs[1] == f"الشرح: {ITEM['explanation']}"
    assert paragraphs[2] == "من فوائد الحديث: - عظم أمر الدماء."  # the empty benefit is dropped
    assert paragraphs[3] == "المراجع: صحيح البخاري (6864)."
    assert "\n" not in snap.answer.replace("\n\n", "")  # one line per section: the chunker keeps it verbatim
    assert snap.content_sha256 == content_hash("", snap.answer)  # what the seed checks before indexing
