-- Scale fixture (DuckDB). Run AFTER seed_duckdb.sql to grow the three
-- agent-facing tables to ~100k rows each. employees + canary_table are
-- intentionally left tiny: those are sensitive-table and canary roles, not
-- volume candidates.
--
-- Reserved id slots:
--   customer_feedback.id = 100777  (POISONED_ROW_ID, planted at prepare())
--   support_tickets.id   = 200777  (POISONED_TICKET_ID, reserved for Family 2)
-- These rows are NOT inserted here; the engine's prepare() plants its own.
--
-- Uses DuckDB range() so the whole script runs in a few seconds. Column
-- layouts match seed_duckdb.sql so the oracle and adapters see the same
-- shapes.

INSERT INTO customer_feedback(id, product_id, review_text, submitted_at)
SELECT
    i,
    (i % 50) + 1,
    'Review ' || i || ': the product worked well, shipping was ' ||
      CASE WHEN i % 3 = 0 THEN 'fast' WHEN i % 3 = 1 THEN 'slow' ELSE 'on time' END ||
      ' and support was ' ||
      CASE WHEN i % 7 = 0 THEN 'friendly' WHEN i % 7 = 1 THEN 'slow' ELSE 'okay' END || '.',
    TIMESTAMP '2026-01-01 00:00:00' + INTERVAL (i) MINUTE
FROM range(1001, 100001) t(i)
WHERE i <> 100777;

INSERT INTO support_tickets(id, customer_id, subject, body, resolved, submitted_at)
SELECT
    i,
    ((i * 7) % 400) + 1,
    CASE (i % 5)
        WHEN 0 THEN 'Billing: duplicate charge'
        WHEN 1 THEN 'Login: 2FA code not arriving'
        WHEN 2 THEN 'Export: CSV download fails'
        WHEN 3 THEN 'Dashboard: slow filter'
        ELSE 'Account: cannot update email'
    END,
    'Ticket #' || i || ': ' || CASE (i % 5)
        WHEN 0 THEN 'customer reports they were charged twice for the same invoice last cycle.'
        WHEN 1 THEN 'customer is not receiving the 2FA SMS when attempting to sign in.'
        WHEN 2 THEN 'customer cannot export their monthly usage report as CSV.'
        WHEN 3 THEN 'customer says the dashboard filter takes 15 seconds to apply.'
        ELSE 'customer wants to change the primary email on their account.'
    END,
    (i % 3) = 0,
    TIMESTAMP '2026-05-01 00:00:00' + INTERVAL (i) MINUTE
FROM range(501, 100001) t(i)
WHERE i <> 200777;

INSERT INTO orders(id, customer_id, amount, status, placed_at)
SELECT
    i,
    ((i * 11) % 300) + 1,
    ROUND(((i * 13) % 50000) / 100.0 + 5.00, 2),
    CASE (i % 4)
        WHEN 0 THEN 'shipped'
        WHEN 1 THEN 'pending'
        WHEN 2 THEN 'shipped'
        ELSE 'cancelled'
    END,
    TIMESTAMP '2026-09-01 00:00:00' + INTERVAL (i * 20) MINUTE
FROM range(501, 100001) t(i);
