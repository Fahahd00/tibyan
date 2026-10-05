from tibyan_ai.privacy.pii import redact


def test_redacts_email_phone_and_national_id():
    r = redact("جوالي 0551234567 وبريدي test.user@example.com وهويتي 1012345678")
    assert "0551234567" not in r.text and "example.com" not in r.text and "1012345678" not in r.text
    assert set(r.types) == {"phone", "email", "national_id"}


def test_redacts_arabic_indic_digits():
    r = redact("رقمي ٠٥٥١٢٣٤٥٦٧")
    assert r.types == ["phone"]


def test_redacts_self_introduced_name_without_eating_next_word():
    r = redact("اسمي محمد بن صالح وجوالي 0551234567")
    assert "محمد" not in r.text
    assert "وجوالي" in r.text


def test_english_name_and_international_phone():
    r = redact("my name is John Smith, call +44 7911 123456")
    assert "John" not in r.text and "7911" not in r.text
    assert set(r.types) == {"name", "phone"}


def test_question_without_pii_is_unchanged():
    q = "هل يجوز قصر الصلاة للمسافر؟"
    r = redact(q)
    assert r.text == q and not r.found
