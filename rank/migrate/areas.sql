INSERT INTO school (code, name, buildings) VALUES ('PANGYO-TV1', '판교 제1테크노밸리', 201) ON CONFLICT (code) DO UPDATE SET name = excluded.name, buildings = excluded.buildings;
INSERT INTO school (code, name, buildings) VALUES ('GANGNAM-YEOKSAM', '강남 역삼', 348) ON CONFLICT (code) DO UPDATE SET name = excluded.name, buildings = excluded.buildings;
INSERT INTO school (code, name, buildings) VALUES ('PANGYO-STATION', '판교 판교역 앞', 108) ON CONFLICT (code) DO UPDATE SET name = excluded.name, buildings = excluded.buildings;
INSERT INTO school (code, name, buildings) VALUES ('PANGYO-TV2', '판교 제2테크노밸리', 228) ON CONFLICT (code) DO UPDATE SET name = excluded.name, buildings = excluded.buildings;
INSERT INTO school (code, name, buildings) VALUES ('YEOUIDO', '여의도 금융가', 221) ON CONFLICT (code) DO UPDATE SET name = excluded.name, buildings = excluded.buildings;
INSERT INTO school (code, name, buildings) VALUES ('GANGNAM-STATION', '강남 강남역', 348) ON CONFLICT (code) DO UPDATE SET name = excluded.name, buildings = excluded.buildings;
INSERT INTO school (code, name, buildings) VALUES ('GANGNAM-SEOLLEUNG', '강남 선릉', 350) ON CONFLICT (code) DO UPDATE SET name = excluded.name, buildings = excluded.buildings;
INSERT INTO school (code, name, buildings) VALUES ('GANGNAM-SAMSEONG', '강남 삼성', 350) ON CONFLICT (code) DO UPDATE SET name = excluded.name, buildings = excluded.buildings;
