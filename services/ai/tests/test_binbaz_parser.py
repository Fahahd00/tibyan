"""Parser tests on a synthetic page that mirrors binbaz.org.sa markup (placeholder text only)."""

import json
import re

from tibyan_ai.ingestion.binbaz import (
    BinbazFetcher,
    content_hash,
    parse_category_page,
    parse_fatwa_page,
    parse_leaf_categories,
)

PAGE = """
<html><body>
<div itemprop="breadcrumb"><ol class="breadcrumb">
  <li><a href="/">home</a></li><li><a href="/fatwas/kind/1">مجموع الفتاوى</a></li><li class="active">عنوان</li>
</ol></div>
<article class="fatwa">
  <h1 class="article-title article-title--primary">عنوان تجريبي</h1>
  <h2 class="article-title article-title__question"><p><strong>السؤال:</strong></p><p>نص سؤال تجريبي؟</p></h2>
  <div itemprop="articleBody" class="article-content">ج: سطر أول من نص تجريبي<br>سطر ثانٍ من نص تجريبي.
    <p>(مرجع تجريبي 1/1).</p></div>
</article></body></html>
"""


def test_parses_text_nodes_and_paragraphs_and_strips_labels():
    snap = parse_fatwa_page(PAGE, "https://binbaz.org.sa/fatwas/1/x", "1")
    assert snap is not None
    assert snap.title == "عنوان تجريبي"
    assert snap.question == "نص سؤال تجريبي؟"
    assert snap.answer == "سطر أول من نص تجريبي\n\nسطر ثانٍ من نص تجريبي.\n\n(مرجع تجريبي 1/1)."
    assert snap.collection == "مجموع الفتاوى"
    assert snap.content_sha256 == content_hash(snap.question, snap.answer)


def test_missing_article_returns_none():
    assert parse_fatwa_page("<html></html>", "u", "1") is None


def test_category_links_are_deduplicated():
    html = (
        '<a href="https://binbaz.org.sa/fatwas/10/a">x</a><a href="https://binbaz.org.sa/fatwas/10/a">x</a>'
        '<a href="https://binbaz.org.sa/fatwas/11/b">y</a><a href="https://binbaz.org.sa/articles/3/c">z</a>'
    )
    assert [i for i, _ in parse_category_page(html)] == ["10", "11"]


def test_leaf_categories_skip_parents():
    html = (
        '<li class="tree__item tree__item--has-children"><a href="https://binbaz.org.sa/categories/fiqhi/9">ط</a>'
        '<ul><li class="tree__item  "><a href="https://binbaz.org.sa/categories/fiqhi/10">م</a></li>'
        '<li class="tree__item  "><a href="https://binbaz.org.sa/categories/fiqhi/11">آ</a></li></ul></li>'
    )
    assert parse_leaf_categories(html) == [10, 11]


def test_crawl_spreads_a_limit_over_categories_and_skips_existing(tmp_path):
    lists = {1: ["10", "11", "12"], 2: ["20", "21"]}
    (tmp_path / "11.json").write_text(json.dumps({"categories": []}), encoding="utf-8")

    class Offline(BinbazFetcher):
        def _get(self, url):
            m = re.search(r"/categories/fiqhi/(\d+)\?page=(\d+)$", url)
            if not m:
                return PAGE
            ids = lists[int(m.group(1))] if m.group(2) == "1" else []
            return "".join(f'<a href="https://binbaz.org.sa/fatwas/{i}/x">x</a>' for i in ids) or None

    stats = Offline(tmp_path, delay_s=0).crawl({1: 2, 2: 2}, limit=3)
    # Round-robin order 10, 20, 11 (existing), 21, 12: the limit cuts 12, not the second category.
    assert stats == {"listed": 5, "fetched": 3, "skipped_existing": 1, "failed": 0}
    assert sorted(p.stem for p in tmp_path.glob("*.json")) == ["10", "11", "20", "21"]
