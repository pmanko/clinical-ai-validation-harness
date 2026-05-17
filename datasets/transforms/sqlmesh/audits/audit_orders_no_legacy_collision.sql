AUDIT (
  name audit_orders_no_legacy_collision,
  dialect mysql
);

-- clin__orders uses obs.obs_id as the order_id (research.md §R-load-pattern
-- — deterministic, clinically traceable, no magic offset). The demo's
-- legacy_27_raw.orders is empty per T021, so no collision risk. If a
-- future corpus has both populated obs AND legacy orders, an overlap
-- could violate the orders PK. This audit catches that scenario early:
-- it fails the pipeline if any clin__orders.order_id appears in
-- legacy_27_raw.orders.order_id.

SELECT
  co.order_id AS colliding_order_id,
  legacy.uuid AS legacy_orders_uuid
FROM refapp_28_demo.clin__orders co
JOIN legacy_27_raw.orders legacy
  ON legacy.order_id = co.order_id
;
