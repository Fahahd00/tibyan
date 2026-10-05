from tibyan_ai.text.arabic import content_terms, light_stem, normalize, search_text, split_sentences
from tibyan_ai.text.language import detect_language


def test_normalize_removes_diacritics_and_unifies_letters():
    assert normalize("الصَّلاةُ") == normalize("الصلاة") == "الصلاه"
    assert normalize("إِلى أحمد آدم") == "الي احمد ادم"
    assert normalize("مُسْتَشْفَى") == "مستشفي"


def test_normalize_expands_honorific_ligature():
    assert "صلي الله عليه وسلم" in normalize("النبي ﷺ")


def test_light_stem_strips_article_and_clitics():
    assert light_stem(normalize("والمسافرين")) == "مسافر"
    assert light_stem(normalize("بالصلاة")) == light_stem(normalize("الصلاة"))


def test_content_terms_drop_stopwords_and_query_noise():
    terms = content_terms("ما حكم قصر الصلاة للمسافر؟", drop_query_noise=True)
    assert terms == ["قصر", "صلا", "مسافر"]
    assert "انا" not in content_terms("وأنا مسافر")


def test_search_text_is_stemmed():
    assert search_text("قصر الصلاة للمسافر") == "قصر صلا مسافر"


def test_sentences_do_not_split_on_arabic_semicolon():
    text = "المسافر إذا نوى الإقامة أكثر من أربعة أيام؛ فهو في حكم المقيمين. والله أعلم بالصواب دائمًا."
    sents = split_sentences(text)
    assert sents[0].endswith("فهو في حكم المقيمين.")


def test_detect_language():
    assert detect_language("هل يجوز قصر الصلاة؟") == "ar"
    assert detect_language("Can a traveller shorten prayer?") == "en"
    assert detect_language("12345", default="en") == "en"
    assert detect_language("کیا میں سفر میں نماز قصر کر سکتا ہوں؟") == "ur"
    assert detect_language("هل يجوز قصر الصلاة؟", default="ur") == "ar"  # Arabic, even in the Urdu interface
    assert detect_language("क्या मैं सफ़र में नमाज़ क़स्र कर सकता हूँ?") == "hi"
    assert detect_language("Yolculukta namazı kısaltabilir miyim?") == "tr"
    # Latin script alone cannot tell Indonesian from English: the interface language decides.
    assert detect_language("Bolehkah saya mengqashar salat?", default="id") == "id"
    assert detect_language("Bolehkah saya mengqashar salat?") == "en"
    assert detect_language("মুসাফির কত দিন নামাজ কসর করতে পারে?") == "bn"
    assert detect_language("Мұсафир намазды қанша уақыт қысқартып оқи алады?") == "kk"
    assert detect_language("Shin ɗawafi ba tare da alwala ba ya inganta?") == "ha"  # Hausa hooked letters
    assert detect_language("Bolehkah saya mengqasarkan solat?", default="ms") == "ms"
    assert detect_language("Namozni qasr qilsam boʻladimi?", default="uz") == "uz"


def test_locate_verbatim_returns_the_source_wording():
    from tibyan_ai.text.arabic import locate_verbatim

    source = "النبيﷺ وقَّت الأوقات، وبيَّنها، فلما بيَّن وقت الظهر"
    assert locate_verbatim(source, "وقت الاوقات وبينها") == "وقَّت الأوقات، وبيَّنها"
    assert locate_verbatim(source, "نص غير موجود") is None


def test_normalize_with_map_matches_normalize_on_the_real_corpus():
    import json
    from pathlib import Path

    from conftest import require_corpus

    from tibyan_ai.text.arabic import normalize_with_map

    corpus = Path(__file__).resolve().parents[3] / "data" / "corpus" / "binbaz"
    files = sorted(corpus.glob("*.json"))[:150]
    require_corpus(files)
    for path in files:
        snap = json.loads(path.read_text(encoding="utf-8"))
        for text in (snap["question"], snap["answer"]):
            norm, origin = normalize_with_map(text)
            assert norm == normalize(text)
            assert len(origin) == len(norm)
