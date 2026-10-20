INSERT INTO settings.tenants (id, name, owner) VALUES
    ('acme', 'Acme (broken feature)', 'architect'),
    ('globex', 'Globex (healthy control)', 'architect')
ON CONFLICT DO NOTHING;

INSERT INTO settings.features (tenant_id, feature_key, enabled) VALUES
    ('acme', 'advanced_reports', false), ('acme', 'notifications', true),
    ('globex', 'advanced_reports', true), ('globex', 'notifications', true)
ON CONFLICT DO NOTHING;

INSERT INTO runtime.features (tenant_id, feature_key, enabled) VALUES
    ('acme', 'advanced_reports', false), ('acme', 'notifications', true),
    ('globex', 'advanced_reports', true), ('globex', 'notifications', true)
ON CONFLICT DO NOTHING;

