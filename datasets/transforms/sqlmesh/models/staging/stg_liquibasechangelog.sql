MODEL (
  name refapp_28_demo.stg_liquibasechangelog,
  kind FULL,
  description 'Staging copy of legacy_27_raw.liquibasechangelog with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (ID, AUTHOR, FILENAME),
  audits ()
);

SELECT
  src.ID,
  src.AUTHOR,
  src.FILENAME,
  @shift_date(src.DATEEXECUTED) AS DATEEXECUTED,
  src.MD5SUM,
  src.DESCRIPTION,
  src.COMMENTS,
  src.TAG,
  src.LIQUIBASE,
  src.ORDEREXECUTED,
  src.EXECTYPE,
  src.CONTEXTS,
  src.LABELS,
  src.DEPLOYMENT_ID
FROM legacy_27_raw.liquibasechangelog src

;
