MODEL (
  name refapp_28_demo.seeds.module_table_policy,
  kind SEED (
    path '../../seeds/module_table_policy.csv'
  ),
  columns (
    table_name VARCHAR(128),
    policy VARCHAR(32),
    rationale VARCHAR(512),
    ticket_ref VARCHAR(128)
  ),
  description 'Per legacy-only table, the reviewed decision: drop / carry-forward / install-module / remap. Default carry-forward; reviewer adjusts at acceptance.',
  tags (policy_bucket:passthrough),
  grain (table_name)
);
