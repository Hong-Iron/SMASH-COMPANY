# Writes migrate/areas.sql: one row per 업무지구 that has a page (code = area id in upper case, as the game sends it).
# usage: python3 rank/areas_sql.py   then   npx wrangler d1 execute smash_company --remote --file migrate/areas.sql
import json, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
areas = json.loads((root / "areas.json").read_text(encoding="utf-8"))
rows = []
for aid, a in areas.items():
    f = root / "data" / f"{aid}.json"
    if not f.exists(): continue
    n = len(json.loads(f.read_text(encoding="utf-8"))["buildings"])
    name = f"{a['district']} {a['name']}".replace("'", "''")
    rows.append(f"INSERT INTO school (code, name, buildings) VALUES ('{aid.upper()}', '{name}', {n}) "
                f"ON CONFLICT (code) DO UPDATE SET name = excluded.name, buildings = excluded.buildings;")
(root / "rank" / "migrate" / "areas.sql").write_text("\n".join(rows) + "\n", encoding="utf-8")
print(len(rows), "areas → rank/migrate/areas.sql")
