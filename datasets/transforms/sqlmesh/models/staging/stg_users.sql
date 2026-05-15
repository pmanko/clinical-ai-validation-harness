MODEL (
  name refapp_28_demo.stg_users,
  kind FULL,
  description 'Staging copy of legacy_27_raw.users with concept-FK columns rebound via the bridge rule.',
  tags (policy_bucket:passthrough),
  grain (user_id),
  audits (unique_values(columns := (user_id)))
);

SELECT
  src.user_id,
  src.system_id,
  src.username,
  src.password,
  src.salt,
  src.secret_question,
  src.secret_answer,
  src.creator,
  src.date_created,
  src.changed_by,
  src.date_changed,
  src.person_id,
  src.retired,
  src.retired_by,
  src.date_retired,
  src.retire_reason,
  src.uuid,
  src.activation_key,
  src.email
FROM legacy_27_raw.users src

;
