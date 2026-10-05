"""Evidence fixtures built from a REAL, verbatim fatwa excerpt (binbaz.org.sa/fatwas/3338)."""

from tibyan_ai.pipeline.retrieval import Candidate

QUESTION_3338 = (
    "نحن قادمون من بلاد بعيدة، ثم نزلنا بالرياض، فهل نعتبر مسافرين تطبق علينا أحكام السفر، أم مقيمين؟"
)
ANSWER_3338 = (
    "المسافر إذا نزل في البلد، وعنده نية الإقامة أكثر من أربعة أيام؛ فهو في حكم المقيمين، يصلي أربعًا، "
    "ولا يجمع إذا كانت نيته الإقامة أكثر من أربعة أيام بلياليها، هذا هو الذي عليه جمهور أهل العلم.\n\n"
    "أما إذا نزل وهو إنما أراد يومًا، أو يومين، أو ثلاثًا فهو مسافر، أو ما عنده يقين، ما يدري متى يسافر، "
    "لا يدري يسافر غدًا، أو بعد غد، يطلب حاجة لا يدري متى يحصلها، أو خصمًا له يطلبه، أو ما أشبه ذلك من "
    "الحاجات التي لا يعلم متى تنتهي، فهذا حكمه حكم المسافرين، ولو عاش سنة ما دام بهذه النية."
)


def evidence(ref: str = "E1", dense: float = 0.8, coverage: float = 1.0) -> Candidate:
    return Candidate(
        chunk_id="00000000-0000-0000-0000-000000000001",
        document_id="00000000-0000-0000-0000-0000000000d1",
        ordinal=0,
        content=f"{QUESTION_3338}\n\n{ANSWER_3338}",
        search_text="",
        title="حكم قصر الصلاة للمسافر ومدته",
        url="https://binbaz.org.sa/fatwas/3338",
        collection="فتاوى الجامع الكبير",
        question=QUESTION_3338,
        external_id="3338",
        source={
            "id": "s",
            "slug": "binbaz",
            "name_ar": "ابن باز",
            "name_en": "Ibn Baz",
            "publisher_ar": None,
            "publisher_en": None,
            "base_url": "https://binbaz.org.sa",
            "status": "approved",
        },
        dense_score=dense,
        coverage=coverage,
        title_coverage=1.0,
        ref=ref,
    )
