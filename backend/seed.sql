-- Seed data for the FIR routing system.
--
-- SEVERITY RUBRIC (defensible on a slide, derived from the CrPC First
-- Schedule classification plus maximum punishment):
--   1-3   non-cognizable or bailable, under 3 years
--   4-6   cognizable, up to 7 years
--   7-8   cognizable and non-bailable, 7+ years
--   9-10  life imprisonment or death
--
-- VERIFY BEFORE THE REVIEW: cognizable/bailable status below follows the
-- CrPC First Schedule, but several sections have state-level amendments
-- (notably 324 and 506). Cross-check the ones you plan to demo and cite
-- the First Schedule in the report. Trim this list to match exactly the
-- sections in Track A's label_set.json.

INSERT INTO ipc_sections (code, title, cognizable, bailable, max_punishment_years, severity_weight) VALUES
('302',  'Murder',                                          1, 0, NULL, 10.0),
('307',  'Attempt to murder',                               1, 0, 10,    9.0),
('304',  'Culpable homicide not amounting to murder',       1, 0, NULL,  9.0),
('304B', 'Dowry death',                                     1, 0, NULL,  9.0),
('376',  'Rape',                                            1, 0, NULL, 10.0),
('366',  'Kidnapping or abducting a woman to compel marriage', 1, 0, 10, 8.0),
('363',  'Kidnapping',                                      1, 1, 7,     6.0),
('354',  'Assault on a woman with intent to outrage modesty',1, 0, 5,    6.0),
('498A', 'Cruelty by husband or his relatives',             1, 0, 3,     6.0),
('395',  'Dacoity',                                         1, 0, NULL,  9.0),
('392',  'Robbery',                                         1, 0, 10,    8.0),
('326',  'Grievous hurt by dangerous weapon',               1, 0, NULL,  8.0),
('325',  'Voluntarily causing grievous hurt',               1, 1, 7,     6.0),
('324',  'Voluntarily causing hurt by dangerous weapon',    1, 0, 3,     5.0),
('323',  'Voluntarily causing hurt',                        0, 1, 1,     2.0),
('420',  'Cheating and dishonestly inducing delivery of property', 1, 0, 7, 6.0),
('419',  'Cheating by personation',                         1, 1, 3,     5.0),
('406',  'Criminal breach of trust',                        1, 0, 3,     5.0),
('467',  'Forgery of a valuable security or will',          1, 0, NULL,  7.0),
('468',  'Forgery for the purpose of cheating',             1, 0, 7,     6.0),
('471',  'Using as genuine a forged document',              1, 1, 7,     5.0),
('379',  'Theft',                                           1, 0, 3,     5.0),
('447',  'Criminal trespass',                               1, 1, 0.25,  1.0),
('506',  'Criminal intimidation',                           0, 1, 7,     4.0),
('201',  'Causing disappearance of evidence',               1, 1, 7,     5.0),
('120B', 'Criminal conspiracy',                             1, 0, NULL,  6.0),
('149',  'Unlawful assembly: common object',                1, 0, NULL,  5.0),
('34',   'Acts done by several persons in common intention',1, 0, NULL,  4.0);

-- ROUTING RULES
-- Lower precedence wins. Victim-centric ordering: offences against women
-- and children outrank general violent crime, so a complaint citing both
-- 302 and 376 routes to Women & Child Protection rather than Crime Branch.

INSERT INTO routing_rules (section_code, unit, precedence) VALUES
-- Women & Child Protection
('376',  'Women & Child Protection Unit', 1),
('354',  'Women & Child Protection Unit', 1),
('366',  'Women & Child Protection Unit', 1),
('498A', 'Women & Child Protection Unit', 1),
('304B', 'Women & Child Protection Unit', 1),
('363',  'Women & Child Protection Unit', 2),

-- Crime Branch: homicide and serious violent crime
('302',  'Crime Branch', 3),
('307',  'Crime Branch', 3),
('304',  'Crime Branch', 3),
('395',  'Crime Branch', 3),
('392',  'Crime Branch', 4),
('326',  'Crime Branch', 4),
('120B', 'Crime Branch', 5),

-- Economic Offences Wing
('420',  'Economic Offences Wing', 5),
('406',  'Economic Offences Wing', 5),
('467',  'Economic Offences Wing', 5),
('468',  'Economic Offences Wing', 5),
('471',  'Economic Offences Wing', 6),

-- Cyber Cell
('419',  'Cyber Cell', 5),

-- Local Police Station: everything else
('325',  'Local Police Station', 7),
('324',  'Local Police Station', 7),
('323',  'Local Police Station', 8),
('379',  'Local Police Station', 7),
('447',  'Local Police Station', 9),
('506',  'Local Police Station', 8),
('201',  'Local Police Station', 8),
('149',  'Local Police Station', 8),
('34',   'Local Police Station', 9);
