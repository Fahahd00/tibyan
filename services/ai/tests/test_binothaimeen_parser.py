"""Parser tests on a synthetic page that mirrors old.binothaimeen.net markup (placeholder text only)."""

from tibyan_ai.ingestion.binbaz import content_hash
from tibyan_ai.ingestion.binothaimeen import (
    category_name,
    parse_category_page,
    parse_fatwa_page,
    parse_leaf_categories,
)

PAGE = """
<html><head><title>الموقع الرسمي لفضيلة الشيخ - عنوان تجريبي - جزء ثان</title></head><body>
<div class='item-term'><div class='voclink'>اسم السلسلة: <span class="white-text"></div>
  <a class="tidlikn" href="?tid=91">سلسلة تجريبية</a><div class='faselterm'>></div>
  <a class="tidlikn" href="?tid=139">سلسلة تجريبية [1]</a></div><div class='clear'></div>
<div class='item-term'><a class="voclink" href="?vid=21">تصنيف فقهي: </a>
  <a class="tidlikn" href="?tid=794">الصلاة</a></div><div class='clear'></div>
<div id="view-list-body-body" class="body-text">
  <div id="mat-parts-c"><div class="part-content"></div></div>
  <div class="custom-hide">
    <p><span class="sidetitle">السؤال :</span></p>
    <p>نص سؤال تجريبي؟</p>
    <p><span class="sidetitle">الجواب: </span></p>
    <p>الشيخ: سطر أول من نص تجريبي.</p>
    <p>سطر ثانٍ من نص تجريبي.</p>
  </div>
</div>
<script>$(document).ready(function () { var x = 1; });</script>
</body></html>
"""


def test_splits_question_and_answer_and_strips_labels():
    snap = parse_fatwa_page(PAGE, "https://old.binothaimeen.net/content/1", "1")
    assert snap is not None
    assert snap.title == "عنوان تجريبي - جزء ثان"
    assert snap.question == "نص سؤال تجريبي؟"
    assert snap.answer == "الشيخ: سطر أول من نص تجريبي.\n\nسطر ثانٍ من نص تجريبي."
    assert snap.collection == "سلسلة تجريبية"
    assert snap.source_slug == "binothaimeen"
    assert snap.content_sha256 == content_hash(snap.question, snap.answer)


def test_content_without_question_and_answer_is_not_a_fatwa():
    lesson = PAGE.replace("السؤال :", "مقدمة").replace("الجواب: ", "تمهيد")
    assert parse_fatwa_page(lesson, "u", "1") is None


def test_listing_ignores_sidebar_links_and_reads_the_current_term():
    html = (
        '<a class="linknewsheader" href="https://old.binothaimeen.net/content/9">خبر</a>'
        '<a class="type-list-item-title" href="https://old.binothaimeen.net/content/10">أ</a>'
        '<a class="type-list-item-title" href="https://old.binothaimeen.net/content/10">أ</a>'
        '<a class="type-list-item-title" href="https://old.binothaimeen.net/content/11">ب</a>'
        '<a class="tidlinkn linkslasel">صلاة المسافر</a>'
    )
    assert [i for i, _ in parse_category_page(html)] == ["10", "11"]
    assert category_name(html) == "صلاة المسافر"


def test_leaf_categories_come_from_the_tree_script():
    tree = (
        "d.add(0, -1, '<a>root</a>', ''); d.add(795, 0, 'الطهارة 713', '/x');"
        "d.add(813, 795, 'المياه 11', '/y'); d.add(793, 0, 'الجهاد 46', '/z');"
    )
    assert parse_leaf_categories(tree) == [813, 793]
