# SMASH 회사

판교, 강남, 여의도, 광화문 같은 업무지구의 실제 회사 건물을 3D로 부수는 모바일 웹 게임이다. SMASH 대학교의 자매 게임이고, 같은 엔진(부서짐·글자·폰트·UI)을 쓴다. 회사들과 관계없는 비공식 패러디다.

**바로 하기:** https://hong-iron.github.io/SMASH-COMPANY/

## 구성

| 폴더 | 하는 일 |
|---|---|
| `src/app.html` | 게임 엔진. SMASH 대학교 엔진 포크(항공사진 땅, 부술 수 있는 건물만 그림, 회사판 글자, 공중에서 시작하는 덩어리) |
| `tools/` | 데이터 받기(`fetch.py`, `vworld.py`), 정리(`prep_area.py`), 엔진 형식으로(`to_smash.py`), 페이지(`assemble.py`), 썸네일(`thumbs.py`), 전부(`build_all.sh`) |
| `hub/` | SMASH 회사 허브(검색·지도·지구별 랭킹·카드). `hub/build.py` → `site/index.html` |
| `rank/` | 지구별 랭킹 서버: Cloudflare Worker + D1 (`smash-company-rank`) |
| `site/` | 공개되는 파일. main에 push하면 GitHub Pages로 배포된다 |
| `areas.json` | 업무지구 목록(기준점, 크기, 지역) |
| `PROMPT.md` | 명세 원본 |

## 업무지구 하나 만들기

```bash
zsh tools/build_all.sh <area>                                   # 받기 → 정리 → 엔진 데이터 → 페이지
~/.venvs/vault-plots/bin/python tools/thumbs.py <area>          # og.jpg, card.webp (로컬 서버 :8790 필요)
~/.venvs/vault-plots/bin/python hub/build.py                    # 허브
python3 rank/areas_sql.py && (cd rank && npx wrangler d1 execute smash_company --remote --file migrate/areas.sql)
```

키(`VWORLD_KEY`, `MAPILLARY_TOKEN`)는 git에 올리지 않는 `.env`에 둔다.

## 출처

- © OpenStreetMap contributors (ODbL)
- 국토교통부 브이월드: 건물 높이·용도·이름, 항공사진 (공공누리 제1유형)
- 지형: AWS Terrain Tiles (Mapzen terrarium)
- 건물 외벽 색: 공개된 사진(회사·설계사·언론)을 보고 고른 값. 사진 자체는 쓰지 않는다
