INSERT INTO support.tenants (id, name, owner) VALUES
    ('acme', 'Acme (broken feature)', 'architect'),
    ('globex', 'Globex (healthy control)', 'architect')
ON CONFLICT DO NOTHING;

INSERT INTO support.requests (id, tenant_id, title, description, owner, document_ids) VALUES
    ('ticket-acme', 'acme', 'Advanced reports unavailable',
     'Acme should have advanced reports enabled. Inspect desired and runtime settings, fix and verify.',
     'junior-2', ARRAY['doc-feature-guide']),
    ('ticket-globex', 'globex', 'Healthy tenant control',
     'Do not change this healthy tenant while fixing Acme.', 'senior', ARRAY['doc-operations']),
    ('ticket-delete-demo', 'acme', 'Review disposable document deletion',
     'Historical document references remain after deletion. Owner approval is a later milestone.',
     'architect', ARRAY['doc-disposable'])
ON CONFLICT DO NOTHING;
