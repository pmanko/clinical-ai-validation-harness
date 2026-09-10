-- Add invented prescription flags needed by the recovered full dashboard.
-- This changes only the isolated synthetic source, preserving the date lab's counts.
DO $$
DECLARE table_name text; column_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY['UTI Individual Current','UTI Individual Historical'] LOOP
    FOREACH column_name IN ARRAY ARRAY['tx___2','tx___3','tx___4','tx___5','tx___6','tx___7',
      'other_tx___1','other_tx___2','other_tx___3','other_tx___4','other_tx___5','other_tx___6',
      'other_tx___7','other_tx___8','other_tx___9','other_tx___10','other_tx___11','other_tx___12'] LOOP
      EXECUTE format('ALTER TABLE v1.%I ADD COLUMN IF NOT EXISTS %I integer DEFAULT 0',table_name,column_name);
    END LOOP;
    EXECUTE format('UPDATE v1.%I SET tx___2=CASE WHEN duration %% 3=0 THEN 1 ELSE 0 END,
      tx___3=CASE WHEN duration %% 3=1 THEN 1 ELSE 0 END,
      tx___5=CASE WHEN duration %% 3=2 THEN 1 ELSE 0 END',table_name);
  END LOOP;
END $$;
