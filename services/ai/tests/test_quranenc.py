import json

from tibyan_ai.ingestion import quranenc
from tibyan_ai.ingestion.binbaz import content_hash
from tibyan_ai.pipeline import live_search

ITEM = {  # shape of https://quranenc.com/api/v1/translation/aya/arabic_moyassar/1/1
    "id": "1",
    "sura": "1",
    "aya": "1",
    "arabic_text": "بِسۡمِ ٱللَّهِ ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ",
    "translation": "أبتدئ قراءة القرآن باسم الله  مستعينا به،\nوهو أخص أسماء الله تعالى.",
    "footnotes": None,
}


def test_a_verse_is_stored_with_its_reference_then_the_tafsir_verbatim(monkeypatch):
    monkeypatch.setattr(quranenc, "sura_names", lambda: {1: "الفاتحة"})
    snap = quranenc.parse_api(json.dumps({"result": ITEM}), "", "1/1")
    assert snap.source_slug == "tafsir-muyassar" and snap.external_id == "1"
    assert snap.url == "https://quranenc.com/ar/browse/arabic_moyassar/1/1"
    assert snap.title == "تفسير سورة الفاتحة — الآية 1" and snap.collection == "سورة الفاتحة"
    verse, tafsir = snap.answer.split("\n\n")
    assert verse == "﴿بِسۡمِ ٱللَّهِ ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ﴾ [الفاتحة: 1]"
    # the publisher's words, only whitespace joined so the chunker keeps the paragraph whole
    assert tafsir == "التفسير الميسر: أبتدئ قراءة القرآن باسم الله مستعينا به، وهو أخص أسماء الله تعالى."
    assert snap.content_sha256 == content_hash("", snap.answer)
    assert quranenc.parse_api(json.dumps({"result": {}}), "", "1/1") is None


def test_live_search_reads_hadith_and_verse_pages_through_their_apis():
    urls = [
        "https://hadeethenc.com/ar/browse/hadith/2962",
        "https://quranenc.com/en/browse/english_saheeh/2/255",  # another translation's page of the verse
        "https://quranenc.com/ar/browse/arabic_moyassar/5#6",
        "https://quranenc.com/ar/browse/arabic_moyassar/5",  # a whole sura: no verse to read
    ]
    pages = live_search.fatwa_pages(urls, {"hadeethenc", "tafsir-muyassar"}, limit=4)
    assert [site.fetch_url(url, ref) for site, url, ref in pages] == [
        "https://hadeethenc.com/api/v1/hadeeths/one/?language=ar&id=2962",
        "https://quranenc.com/api/v1/translation/aya/arabic_moyassar/2/255",
        "https://quranenc.com/api/v1/translation/aya/arabic_moyassar/5/6",
    ]
