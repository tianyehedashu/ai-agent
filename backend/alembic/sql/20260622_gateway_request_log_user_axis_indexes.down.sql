-- =============================================================================
-- revision: 20260622_grl_user_ix | 方向: DOWNGRADE (down.sql)
-- =============================================================================

DROP INDEX IF EXISTS ix_gateway_request_logs_vkey_time_notnull;
DROP INDEX IF EXISTS ix_gateway_request_logs_user_platform_inbound;
