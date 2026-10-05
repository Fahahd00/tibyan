-- A source's precedence when fatwas of different sources disagree (1 = highest), from the governance registry.
-- Kept here so the API can show it; retrieval reads it from the registry.

ALTER TABLE sources ADD COLUMN priority integer;
