# SMASH 회사

업무지구의 실제 회사 사옥을 3D로 부수는 모바일 웹 게임. SMASH 대학교의 자매 게임이다. 명세 원본은 `PROMPT.md`다.

## 데이터와 모델 만들기

| 단계 | 명령 | 나오는 것 |
|---|---|---|
| 1. 받기 | `python3 tools/fetch.py <area>` | `raw/<area>/osm.json`, `raw/<area>/dem/` (OSM, AWS terrarium) |
| 2. 정리 | `~/.venvs/vault-plots/bin/python tools/prep_area.py <area>` | `raw/<area>/prep.json`, `raw/<area>/ground.png` |
| 3. 공용 외벽 | `~/.venvs/vault-plots/bin/python tools/make_textures.py` | `site/tex/*.webp` (사진이 없는 건물용) |
| 4. 모델 | `/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P tools/build_area.py -- <area> [--preview]` | `site/areas/<area>/scene.glb`, `meta.json` |

구역 목록은 `areas.json`. 키(`VWORLD_KEY`, `MAPILLARY_TOKEN`)는 git에 올리지 않는 `.env`에 둔다.

## 출처

- © OpenStreetMap contributors (ODbL)
- 지형: AWS Terrain Tiles (Mapzen terrarium, 출처별 표시)
- 국토교통부 브이월드 (공공누리 제1유형)
- 거리 사진 텍스처: Mapillary (CC BY-SA 4.0) — 이 사진으로 만든 텍스처는 CC BY-SA 4.0으로 공개한다
