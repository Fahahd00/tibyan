-- Arabic versions of a source's approval basis and usage note, shown on the Arabic sources page.
-- The existing approval_basis / license_note columns keep the English text.

ALTER TABLE sources ADD COLUMN approval_basis_ar text;
ALTER TABLE sources ADD COLUMN license_note_ar text;
