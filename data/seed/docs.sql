INSERT INTO docs.documents (id, title, body, owner) VALUES
    ('doc-feature-guide', 'Troubleshoot tenant features',
     'Inspect desired settings through Service MCP and applied settings through Service API. Correct desired configuration, then reload the tenant. Missing applied settings mean disabled.',
     'junior-2'),
    ('doc-operations', 'Operations policy', 'Use a ticket to track tenant configuration changes.', 'senior'),
    ('doc-disposable', 'Disposable deletion example', 'Synthetic document for the human deletion demonstration.', 'architect')
ON CONFLICT DO NOTHING;

