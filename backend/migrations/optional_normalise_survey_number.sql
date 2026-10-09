-- Optional, NOT a numbered migration. Run manually if you want existing rows
-- tidied; the app already treats '' and NULL the same on read.
UPDATE cases SET survey_number = NULL WHERE btrim(survey_number) = '';
