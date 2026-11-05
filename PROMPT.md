# SMASH 회사 — build prompt (v2)

Source of truth for the game, written in the "Marigold Park" format ([[_시스템/프롬프트 템플릿/게임 빌드 프롬프트|게임 빌드 프롬프트]]). Decisions come from [[_시스템/게임 개발/디렉터 회의록|디렉터 회의록]] 안건 2. When a playtest finds a problem, fix the code AND rewrite the matching sentence here (never append "also fix …"). Decisions also from 안건 3–4. Lines marked **[제안]** are not yet confirmed by the user; everything else is.


> **v2 (2026-11-06, 사용자 지시): 건물이 부서지는 로직, 텍스트, 폰트, UI는 SMASH 대학교와 동일하게 한다.** 게임 엔진은 SMASH 대학교의 `src/app.html`(three 0.160)을 그대로 가져와 쓴다. 건물은 엔진이 OSM·브이월드 데이터로 직접 만들고 조각내므로, 아래 LOOK의 "Blender로 건물 모델링·chunk id·per-chunk visibility texture" 문장은 대체되었다(블렌더는 무기·소품 모델에 쓴다). 데이터는 `tools/to_smash.py`가 SMASH 형식(`data/<area>.json`)으로 바꾸고, 건물마다 엔진의 `look`(style·wall·glass)을 지붕 사진 색과 외벽 선택으로 정한다. 엔진 변경은 세 가지뿐이다: 땅에 브이월드 항공사진을 그림, 부술 수 없는 건물을 무기 대상 밖의 회색 덩어리로 그림, 글자(무기 이름 사직서·가발·엑셀·결재·월요병·퇴사, 학교→회사, 캠퍼스→업무지구). 거인(7)은 SMASH 그대로 두었다. 뜨거운 커피는 아직 자리가 없다.

```text
PROMPT

Build a mobile-first browser game, "SMASH 회사": a sister game of SMASH 대학교 and a stylised-realistic 3D office-district destruction sandbox, where you smash real office towers in Korea's business districts with office weapons (you pick a district and a weapon and tap, swipe or drag; the physics breaks floors, drops unsupported storeys and adds up the damage in won). Every bit of damage counts toward the building's company and the district on a shared national leaderboard. No fail state, no tutorial: the link opens straight into a district with the first weapon in hand. three.js 0.187.0 from jsDelivr via an import map, no build step for the player: site/index.html plus, per sub-area, site/areas/<id>/scene.glb (meshopt-compressed) and its textures, and site/models/props.glb, all built offline by Blender scripts in tools/ from OpenStreetMap, AWS Terrain Tiles and VWorld data and aerial imagery. Same product shape as SMASH 대학교 (opens straight into play, escalating weapons, style rank, share card, group leaderboard, request issues, support row) with new code written from this prompt.

LOOK
Render: full resolution capped at devicePixelRatio 2 (1.5 on phones), adaptive scale down to 0.6 when a 1 s average frame takes over 20 ms, so mid-range phones hold 60 fps. Post pass on desktop only: UnrealBloomPass at half resolution (strength 0.4, threshold 0.85, only fire, coffee steam and lit windows bloom) then OutputPass with Neutral tone mapping; phones render straight with renderer tone mapping and no composer.
Camera: perspective 45 degrees orbiting the sub-area centre; drag rotates, pinch or wheel zooms from 120 m to 1,400 m, two-finger drag pans; tilt clamped between 25 and 75 degrees above the horizon, so the camera never goes under the street or straight overhead. Far plane 6 km and fog starting at 1.2 km in the sky colour, so the edge of the loaded box melts into haze instead of ending at a cliff. Tapping a building eases the camera to frame it (0.6 s).
Time of day follows the real KST clock by default, toggle to pick: 출근 (08:00, low warm sun from the east, long shadows), 점심 (12:30, high white sun), 퇴근 (18:30, orange sunset, half the windows lit), 야근 (23:00, night sky, 30% of windows lit at random, street lamps). Light changes ease over 2 s. One directional sun with a 2048 shadow map (1024 on phones) fitted to the current view, plus a cool sky / warm ground hemisphere light.
Buildings (Blender, tools/build_area.py run with Blender 5.2 -b): footprints from OSM, heights, floors, use and names from VWorld; each building is modelled, not just extruded: a podium (ground floor 5 m tall with a recessed shop-front or lobby glass band) under the tower body, a parapet 1.2 m tall around the roof, rooftop plant boxes and a lift core on anything over 8 floors, setbacks where OSM gives building:part. Facades are textured per building from real photos of that building (Mapillary street photos, CC BY-SA 4.0, projected onto each wall and rectified; VWorld 3D building textures if their terms allow), packed into one or two 4096 px WebP atlases per sub-area; buildings with no usable photo fall back to a shared 2048 px facade set with three kinds, UV-mapped in world metres so every window lines up with a 3.5 m storey and a 3 m bay: curtain-wall glass (height over 60 m, blue-grey with mullions), banded concrete with window strips (mid-rise offices), warm plaster with shop fronts (low commercial). Roofs below 60 m are UV-projected straight down into the aerial photo, so real roof colours, solar panels and rooftop clutter show; towers above 60 m use the photo's median roof colour plus modelled plant, because aerial photos lean tall buildings off their footprints. A short ambient-occlusion bake darkens facade bottoms and the ground under every building.
Chunks: each smashable building is cut in Blender into chunks 8 m wide and two storeys (7 m) tall; every vertex carries a chunk id attribute, buildings are merged into one mesh per material, and the game hides a broken chunk through a per-chunk visibility texture and spawns its debris, so a whole sub-area draws in a handful of calls.Off-limits buildings: homes and apartments, government offices, embassies, police, military, hospitals, schools, religious buildings and heritage sites are drawn as plain grey blocks with a diagonal hatch; every weapon passes them without damage and the label reads "부술 수 없는 건물". They stay visible so the city has no holes.
Ground: the terrain mesh from AWS Terrain Tiles (terrarium, zoom 15, 8 m grid) draped with the VWorld aerial photo (zoom 18, about 0.6 m per pixel, one 4096 px texture per sub-area), so real roads, crossings, plazas and parks appear; OSM roads add a slight darkening and lane paint only where the photo is blurry; instanced low-poly street trees from OSM; the Han river as a water plane with a soft shader where a box touches it (여의도, 성수, 잠실); outside the box the photo fades into a blurred ring and fog. No people anywhere, no vehicles in v0. Attribution in the menu: OpenStreetMap contributors (ODbL), 국토교통부 브이월드 (공공누리 제1유형), AWS Terrain Tiles sources.Destruction: hits break chunks into 4-8 debris shards with simple physics (gravity, bounce on the ground, friction); chunks that lose all support below drop and break on landing, so no storey ever floats. Dust puffs and paper sheets flutter out of broken office floors. Debris caps: 1,500 live shards on phones, 4,000 on desktop; shards settle and fade after 8 s.
Weapon props (Blender, tools/build_props.py run with Blender 5.2 -b → site/models/props.glb, named nodes envelope, cup, lid, wig, stamp, button): resignation envelope with "사직서" on its face, paper coffee cup with lid and sleeve, a side-parted brown wig, a giant red approval stamp with a wooden handle, a red dome button on a grey box labelled "퇴사". Under 600 triangles each, vertex colours only.

GAME
Districts and sub-areas: each sub-area is a 1.2 x 1.2 km box centred on its anchor, loaded on demand. v0 list (bounds checked with the user at the data step):
  판교: 판교역 앞, 제1테크노밸리, 제2테크노밸리
  여의도: 여의도역 (IFC·파크원), 증권가 (한국거래소 일대)
  강남: 강남역, 역삼, 선릉, 삼성 (코엑스)
  도심: 광화문, 시청·을지로
  잠실: 잠실역
  성수: 성수역
  마곡: 마곡나루역
  G밸리: 구로디지털단지, 가산디지털단지
  상암: 디지털미디어시티
More districts and sub-areas are added from players' requests, like SMASH 대학교 schools.
Data (offline, Python + Blender): tools/fetch.py pulls OSM (Overpass) and terrarium tiles for the box; tools/vworld.py pulls VWorld building data (LT_C_BLDGINFO: height, floors, main use, name) and Satellite WMTS tiles into a mosaic (key VWORLD_KEY in a git-ignored .env, never in the client); tools/build_area.py (Blender) models, chunks, bakes and exports. Each building keeps id, footprint, height, floors, name, use, smashable flag and an optional company tag in site/areas/<id>/meta.json. Company tags come from public company headquarters addresses matched to the building at that address, and from the building name; buildings with no match show their building name only. Each sub-area stays under 6 MB on the wire (glb plus WebP textures; a 1,600 px ground texture on phones).
Weapons (bottom bar, all available from the start, one selected at a time):
  1 사직서 (tap): the envelope is thrown from the camera on a low arc and spins like a shuriken, sticks into the facade, bursts after 0.4 s with radius 10 m and a burst of paper. Cooldown 0.2 s, so rapid tapping feels like a barrage.
  2 뜨거운 커피 (tap): the cup is lobbed, splashes with radius 16 m on impact and the coffee runs down the facade for 2.5 s, melting every chunk it touches from the top down, with steam.
  3 부장님 가발 (swipe): the wig spins along the swipe direction at the height under the finger, slices a 3 m tall band through chunks up to 140 m out, then flies back like a boomerang and slices again. Cooldown 1.5 s.
  4 결재 도장 (tap): a red square shadow marks the spot for 1.0 s, then the stamp drops from the sky, crushes a 28 x 28 m footprint all the way down and leaves a red "반려" seal on the ground.
  5 엑셀 레이저 (drag): draw a path on the ground; after a 0.6 s charge (the sky dims and a green cell grid flickers along the path) a beam of spreadsheet cells sweeps it, cutting a 6 m trench; path length capped at max(520 m, sub-area diagonal x 0.9), the line turns yellow and a toast says so at the cap.
  6 월요병 (tap): magnitude 8.4-9.6 earthquake for 3 s across the whole sub-area, ground wave in the vertex shader, weak lower storeys give way first.
  7 퇴사 (hold the big red button 0.8 s): nuclear blast with radius 380 m at the screen centre, mushroom cloud, one white flash (shortened when 효과 줄이기 is on). Cooldown 25 s with a visible ring, so it stays the finale, not the default.
Damage in won: every chunk is worth its volume x 15,000원 (a 30-storey tower is a few billion won), shown as a rising "+n원" counter and summed per session.
Rank (직급): a style meter fed by damage per second that decays after 2 s idle: 인턴 → 사원 → 대리 → 과장 → 차장 → 부장 → 사장. A caption "승진! 과장" and a stamp sound mark each step up; the top rank shown on the share card is the highest reached this session.
Shared HP **[제안]**: each smashable building has a daily national HP of 50 x its value; damage from every player that day counts against it. A building whose HP reaches 0 collapses to rubble in everyone's view until 09:00 KST the next day, with "오늘 무너짐" on its label. Tuned so the ten most-hit buildings fall on a normal day.
Leaderboards: 오늘 가장 많이 부서진 회사, 오늘 가장 많이 부서진 업무지구, and all-time versions; a player's damage counts toward whatever they hit (no employee / outsider split).
Server: a Cloudflare Worker + D1 forked from smash-rank. The client batches damage per building and sends at most once every 60 s and on pagehide (keepalive); the board and the HP state are cached 60 s. Guards: per-IP daily and per-second caps, per-building per-IP caps, values over the physical maximum dropped. If the server is unreachable the game plays on and shows "순위 잠시 멈춤".
Edge cases: switching sub-area resets the local scene but keeps the session total; a fully flattened sub-area offers "다시 세우기" (rewind animation) and a nudge to another sub-area; off-limits buildings never take damage from any weapon, including 퇴사 and 월요병.

UI
On the canvas (portrait 390 x 844 first, safe-area insets respected): top bar with the sub-area name and a 업무지구 button, the session damage counter, the rank meter; when a building is targeted, its name, company tag and shared HP bar; a one-line board strip "○○ 오늘 n위 · (n-1)위까지 m원"; bottom weapon bar in two rows of four (seven weapons and 공유), every button at least 48 px, all within the bottom third so one thumb reaches.
업무지구 screen: search box "우리 회사 찾기" (building names, company tags, initial consonants) with instant results, a map of Seoul and 성남 with district pins, cards per sub-area with a thumbnail; choosing one loads it in place.
Share: a 1080 x 1350 card (sub-area, building, damage in won, top rank, a render of the wreck) sent through navigator.share with the file on phones, else save and copy link; deep links ?a=<sub-area>&b=<building> open straight on that building.
Menu (one button, top right): time of day, sound, vibration, 효과 줄이기, 품질 (auto / low / high), 다시 세우기, request a district or company (opens a GitHub issue form), credits and the line "회사와 관계없는 비공식 패러디 게임이에요. 회사가 요청하면 내립니다." plus a support row like SMASH 대학교.
Desktop: same layout widened; keys 1-7 weapons, R rewind, M menu, mouse drag orbit, wheel zoom.
Audio: procedural WebAudio, no files: paper whoosh and burst, splash and sizzle, wig whirr, stamp "쾅", laser hum with keyboard clicks, quake rumble, nuke boom, crumbling concrete and glass; office ambience (distant phones, printer) at low volume; music off by default. Vibration on hits, separate toggle. Pause and mute when the page is hidden.
Analytics: GoatCounter (site sassafras) page views plus events prefixed "sc-" (weapon-use first per session, share-open, share-done, search, search-go, area-open, request, support).

QUALITY BAR
Headless bot test through window.__sc (load, setArea, fire, step, state, bench): for every sub-area, load it and fire each weapon 20 times at random smashable buildings; no console errors, no stuck states, no chunk left floating 3 s after a hit, live shards never above the cap, damage totals only go up, off-limits buildings take zero damage, sub-area download under 6 MB on the wire, under 60 draw calls and 600k triangles at the default view, no horizontal scroll at 375 px, share card renders, the client sends at most one damage request per 60 s.
Must work in Safari on iPhone and inside the KakaoTalk, Instagram, X and Everytime in-app browsers (sound unlocks on first tap, share falls back to copy link).
No people, no logos, no real persons' names, no plane-into-building imagery, no real disaster sites; leaderboard wording states facts only ("가장 많이 부서진").
No personal data, keys or paths in the source; the only external requests are jsDelivr (three.js), the ranking Worker and GoatCounter.
```

## Change log

| 날짜 | 바뀐 것 | 이유 |
|---|---|---|
| 2026-11-06 | v2: 엔진·부서짐·글자·폰트·UI를 SMASH 대학교와 동일하게 (엔진 포크), 블렌더 건물 대체 | 사용자 지시 |
| 2026-11-06 | v1.1: 외벽은 건물마다 실제 사진 텍스처, 공용 텍스처는 대체용 | 회의록 안건 5 |
| 2026-11-06 | v1: 이름 확정, 블렌더 모델링 + OSM·AWS 지형·항공사진 텍스처 | 회의록 안건 4 |
| 2026-11-06 | v0 작성 | 회의록 안건 2: 직원/외부 구분 없음, 업무지구·세부 구역 단위, 회사 물건 무기, SMASH 형식 참고·새로 작성 |
