-- The three fallback fatwa authorities were removed from the approved sources on 2026-10-06 and live search no longer
-- reads their websites. Their rows go, and with them (ON DELETE CASCADE) every page live search had indexed from them.

DELETE FROM sources WHERE slug IN ('dar-alifta', 'aliftaa-jo', 'eftaa-kw');
