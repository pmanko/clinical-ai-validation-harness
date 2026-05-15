AUDIT (
  name audit_policy_bucket_coverage,
  dialect mysql
);

-- Every legacy-only table in module_table_policy is accounted for: either
-- its policy is one of the accepted values, or it shows up as a failing
-- row here for reviewer escalation. Non-blocking — this is the FR-008(b)
-- iterative-review surface, not a hard determinism gate.

SELECT
  mt.table_name,
  mt.policy AS unhandled_policy
FROM refapp_28_demo.seeds.module_table_policy mt
WHERE mt.policy NOT IN ('drop', 'carry-forward', 'install-module', 'remap')
;
