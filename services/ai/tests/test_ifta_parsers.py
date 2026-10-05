"""Parser tests on synthetic pages that mirror each fallback authority's markup (placeholder text only)."""

from tibyan_ai.ingestion.binbaz import content_hash
from tibyan_ai.ingestion.ifta_sites import parse_aliftaa_jo, parse_dar_alifta, parse_eftaa_kw

DAR_ALIFTA = """<html><body><div class="fatwa-details"><h2>عنوان تجريبي</h2>
<div class="content"><div><span class="text-gold">من فتاوى:</span><span> فضيلة المفتي التجريبي</span></div></div>
<div class="question-answer"><div class="fatwa-img"><img alt="x"></div>
<label>السؤال:</label><p>نص سؤال تجريبي؟</p>
<label>الجواب:</label><p>فقرة أولى من الجواب.</p><p>فقرة ثانية من الجواب.</p>
<label>اقرأ أيضا :</label><ul><li>رابط آخر</li></ul></div></div></body></html>"""

ALIFTAA_JO = """<html><head><title>
  دار الإفتاء -  عنوان - بشرطة
</title></head><body>
<h4>السؤال:</h4><span id="txtQuestionText"><p> نص سؤال تجريبي؟</p></span>
<h4>الجواب:</h4><span id="txtBody"><p>الجواب التجريبي.</p><p>والله تعالى أعلم.</p></span></body></html>"""

EFTAA_KW = """<html><head><title>إدارة الإفتاء | عنوان تجريبي.</title></head><body>
<div id="ctl00_PlaceHolderMain_Content__ControlWrapper_RichHtmlField">
<p>الحمد لله، وبعد: فقد عـرض على لجنة الفتوى الاستفتاء، ونصه: نص سؤال تجريبي؟</p>
<p>وقد أجابت اللجنة بالتالي: الجواب التجريبي. والله أعلم.</p></div></body></html>"""


def test_dar_alifta_keeps_question_and_answer_apart_and_stops_at_related_links():
    snap = parse_dar_alifta(DAR_ALIFTA, "https://www.dar-alifta.org/ar/fatwa/details/1/x", "1")
    assert snap is not None and snap.source_slug == "dar-alifta"
    assert snap.title == "عنوان تجريبي"
    assert snap.question == "نص سؤال تجريبي؟"
    assert snap.answer == "فقرة أولى من الجواب.\n\nفقرة ثانية من الجواب."
    assert snap.collection == "فضيلة المفتي التجريبي"
    assert snap.content_sha256 == content_hash(snap.question, snap.answer)


def test_aliftaa_jo_reads_the_named_fields():
    snap = parse_aliftaa_jo(ALIFTAA_JO, "https://aliftaa.jo/fatwa/7/", "7")
    assert snap is not None
    assert snap.title == "عنوان - بشرطة"
    assert snap.question == "نص سؤال تجريبي؟"
    assert snap.answer == "الجواب التجريبي.\n\nوالله تعالى أعلم."


def test_eftaa_kw_splits_the_committee_template():
    snap = parse_eftaa_kw(EFTAA_KW, "https://eftaa.awqaf.gov.kw/ar/x-9", "9")
    assert snap is not None
    assert snap.title == "عنوان تجريبي."
    assert snap.question == "نص سؤال تجريبي؟"
    assert snap.answer == "الجواب التجريبي. والله أعلم."


def test_pages_that_are_not_fatwas_are_rejected():
    article = EFTAA_KW.replace("ونصه:", "").replace("أجابت اللجنة بالتالي:", "")
    assert parse_eftaa_kw(article, "u", "9") is None
    assert parse_dar_alifta("<html><body><h2>x</h2></body></html>", "u", "1") is None
    assert parse_aliftaa_jo("<html></html>", "u", "1") is None
