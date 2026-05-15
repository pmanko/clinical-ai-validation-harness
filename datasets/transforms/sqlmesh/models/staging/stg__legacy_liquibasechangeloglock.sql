MODEL (
  name refapp_28_demo.staging.stg__legacy_liquibasechangeloglock,
  kind FULL,
  description 'Staging copy of legacy_27_raw.liquibasechangeloglock with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (ID),
  audits (unique_values(columns := (ID)))
);

SELECT
  src.ID,
  src.LOCKED,
  src.LOCKGRANTED,
  src.LOCKEDBY
FROM legacy_27_raw.liquibasechangeloglock src

;
