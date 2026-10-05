from types import SimpleNamespace as NS

from tibyan_ai.pipeline import live_search, orchestrator
from tibyan_ai.pipeline.orchestrator import PipelineResult


def test_result_urls_prefer_cited_pages_then_consulted_sources():
    resp = NS(
        output=[
            NS(
                type="web_search_call",
                action=NS(sources=[NS(url="https://binbaz.org.sa/fatwas/2/b"), {"url": "https://x.org/1"}]),
            ),
            NS(
                type="message",
                content=[
                    NS(
                        text="https://binbaz.org.sa/fatwas/1/a.\nhttps://binbaz.org.sa/fatwas/2/b?utm_source=x",
                        annotations=[NS(type="url_citation", url="https://binbaz.org.sa/fatwas/1/a")],
                    )
                ],
            ),
        ]
    )
    assert live_search.result_urls(resp) == [
        "https://binbaz.org.sa/fatwas/1/a",
        "https://binbaz.org.sa/fatwas/2/b",
        "https://x.org/1",
    ]


def test_only_fatwa_pages_of_the_searched_tier_are_fetched():
    urls = [
        "https://binbaz.org.sa/categories/fiqhi/50",  # a category page, not a fatwa
        "https://binothaimeen.net/content/1124",  # fetched from the HTML edition
        "https://www.dar-alifta.org/ar/fatwa/details/11050/x",  # fallback tier: not searched now
        "https://binbaz.org.sa/fatwas/4299/y",
        "https://binbaz.org.sa/fatwas/4299/y-again",
    ]
    pages = live_search.fatwa_pages(urls, {"binbaz", "binothaimeen"}, limit=4)
    assert [(site.slug, fatwa_id) for site, _, fatwa_id in pages] == [
        ("binothaimeen", "1124"),
        ("binbaz", "4299"),
    ]
    site, url, fatwa_id = pages[0]
    assert site.fetch_url(url, fatwa_id) == "https://old.binothaimeen.net/content/1124"


def _result(outcome: str, code: str | None = None) -> PipelineResult:
    payload = {"outcome": outcome, "reason": {"code": code} if code else None, "question": {"text": "سؤال"}}
    return PipelineResult(payload=payload, trace={"stages": [{"key": "retrieval"}]})


def _wire(monkeypatch, answers: list[PipelineResult], found: dict[bool, list]):
    calls = {"once": [], "search": []}

    def fake_once(**kw):
        calls["once"].append(kw.get("slugs"))
        return answers.pop(0)

    def fake_search(question, *, primary):
        calls["search"].append(primary)
        return found[primary]

    monkeypatch.setattr(orchestrator, "_ask_once", fake_once)
    monkeypatch.setattr(live_search, "enabled", lambda: True)
    monkeypatch.setattr(live_search, "primary_slugs", lambda: ["binbaz", "binothaimeen"])
    monkeypatch.setattr(live_search, "search_and_ingest", fake_search)
    monkeypatch.setattr(live_search, "tier_domains", lambda primary: {"dar-alifta": ["dar-alifta.org"]})
    monkeypatch.setattr(live_search, "has_documents", lambda slugs: False)
    return calls


def test_answer_from_the_index_needs_no_search(monkeypatch):
    calls = _wire(monkeypatch, [_result("answer")], {True: [], False: []})
    orchestrator.ask(text="سؤال", persist_result=False)
    assert calls == {"once": [["binbaz", "binothaimeen"]], "search": []}


def test_primary_websites_are_searched_before_the_fallback_authorities(monkeypatch):
    page = {"source": "binbaz", "title": "t", "url": "u", "status": "new"}
    calls = _wire(
        monkeypatch,
        [_result("abstention", "weak_evidence"), _result("answer")],
        {True: [page], False: [page]},
    )
    result = orchestrator.ask(text="سؤال", persist_result=False)
    assert calls == {"once": [["binbaz", "binothaimeen"]] * 2, "search": [True]}
    assert [st["key"] for st in result.trace["stages"]] == ["live_search", "retrieval"]


def test_fallback_authorities_are_used_only_when_the_primary_ones_have_nothing(monkeypatch):
    page = {"source": "dar-alifta", "title": "t", "url": "u", "status": "new"}
    calls = _wire(
        monkeypatch,
        [_result("abstention", "no_source"), _result("answer")],
        {True: [], False: [page]},
    )
    orchestrator.ask(text="سؤال", persist_result=False)
    # Second attempt searches every approved source (fallback fatwas included).
    assert calls == {"once": [["binbaz", "binothaimeen"], None], "search": [True, False]}


def test_refusals_that_are_not_about_missing_sources_never_search(monkeypatch):
    calls = _wire(monkeypatch, [_result("abstention", "out_of_scope")], {True: [], False: []})
    orchestrator.ask(text="كيف أطبخ الكبسة؟", persist_result=False)
    assert calls["search"] == []


def test_every_source_with_a_relevant_fatwa_gets_a_slot():
    from fixtures import evidence

    from tibyan_ai.pipeline.retrieval import select_evidence

    ranked = []
    for i, slug in enumerate(["binbaz", "binbaz", "binbaz", "binbaz", "binothaimeen"]):
        c = evidence(f"R{i}")
        c.document_id, c.source = f"doc{i}", {**c.source, "slug": slug}
        ranked.append(c)
    chosen = select_evidence(ranked, top_k=3)
    # The lower-ranked Ibn Uthaymeen fatwa is kept; order stays by rank.
    assert [c.ref for c in chosen] == ["R0", "R1", "R4"]


def test_other_fatwas_answering_the_question_are_listed_once_and_never_the_quoted_one():
    from tibyan_ai.pipeline.generation import Draft
    from tibyan_ai.pipeline.orchestrator import _also_answered

    evidence = [
        {"ref": "E1", "url": "https://binbaz.org.sa/fatwas/1"},
        {"ref": "E2", "url": "https://binbaz.org.sa/fatwas/1"},  # second chunk of the quoted fatwa
        {"ref": "E3", "url": "https://old.binothaimeen.net/content/9"},
        {"ref": "E4", "url": "https://old.binothaimeen.net/content/9"},  # same fatwa again
        {"ref": "E5", "url": "https://binbaz.org.sa/fatwas/7"},  # not answering
    ]
    draft = Draft(mode="llm", answering_refs=["E1", "E2", "E3", "E4"])
    kept = [{"evidence_refs": ["E1"]}]
    assert _also_answered(draft, kept, evidence) == ["E3"]


def test_a_cross_source_conflict_is_settled_by_the_highest_priority_source():
    from fixtures import evidence

    from tibyan_ai.pipeline.orchestrator import top_priority

    baz, othaimeen, egypt = evidence("E1"), evidence("E2"), evidence("E3")
    baz.source["priority"], othaimeen.source["priority"], egypt.source["priority"] = 1, 2, 3
    assert [c.ref for c in top_priority([othaimeen, baz, egypt])] == ["E1"]
    assert [c.ref for c in top_priority([othaimeen, egypt])] == ["E2"]


def test_the_answer_is_rewritten_from_ibn_baz_when_it_quotes_another_source_although_he_answers():
    from fixtures import evidence

    from tibyan_ai.pipeline.generation import Draft, DraftClaim
    from tibyan_ai.pipeline.orchestrator import needs_priority_rerun

    baz, othaimeen = evidence("E1"), evidence("E2")
    baz.source["priority"], othaimeen.source["priority"] = 1, 2

    def draft(*claim_refs, answering=("E1", "E2"), conflict=False):
        claims = [DraftClaim("detail", "t", list(refs), "q") for refs in claim_refs]
        return Draft(mode="llm", claims=claims, conflict=conflict, answering_refs=list(answering))

    assert not needs_priority_rerun(draft(["E1"]), [baz, othaimeen])  # Ibn Baz quoted
    assert needs_priority_rerun(
        draft(["E1", "E2"], ["E2"]), [baz, othaimeen]
    )  # a claim rests on Ibn Uthaymeen only
    assert not needs_priority_rerun(
        draft(["E2"], answering=["E2"]), [baz, othaimeen]
    )  # Ibn Baz does not answer
    assert needs_priority_rerun(draft(["E1"], conflict=True), [baz, othaimeen])
    assert not needs_priority_rerun(
        draft(["E2"], conflict=True), [othaimeen]
    )  # one source: nothing to defer to
