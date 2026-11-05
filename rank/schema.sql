-- SMASH 학교 대항 랭킹 (Cloudflare D1 = SQLite). 다시 실행해도 안전하다(표가 있으면 그대로 둔다)
-- 브라우저는 표를 직접 만지지 못하고, Worker의 두 주소(smash_add, smash_board)만 부른다

-- 게임이 있는 학교. 목록에 없는 코드로 보낸 점수는 버린다
CREATE TABLE IF NOT EXISTS school (
  code TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  buildings INTEGER NOT NULL CHECK (buildings > 0)
);

-- 날짜(한국 시간)별 학교 합계. ips = 그날 이 학교에 점수를 보낸 IP 수(학교 하루 상한 계산에 쓴다)
CREATE TABLE IF NOT EXISTS daily (
  day TEXT NOT NULL,
  code TEXT NOT NULL,
  score INTEGER NOT NULL DEFAULT 0,
  kills INTEGER NOT NULL DEFAULT 0,
  players INTEGER NOT NULL DEFAULT 0,
  ips INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, code)
);

-- 학교별 전체 합계. 순위표가 날짜별 표 전체를 훑지 않도록 점수를 더할 때 같이 더한다
CREATE TABLE IF NOT EXISTS total (
  code TEXT PRIMARY KEY,
  score INTEGER NOT NULL DEFAULT 0,
  kills INTEGER NOT NULL DEFAULT 0,
  players INTEGER NOT NULL DEFAULT 0
);

-- IP(날짜와 섞은 해시) × 날짜 × 학교 한 줄: 하루 합계, 토큰 버킷(한 번에 300만, 초당 5만씩 참), 1분 창의 전송 횟수
CREATE TABLE IF NOT EXISTS ipday (
  k TEXT NOT NULL,
  day TEXT NOT NULL,
  code TEXT NOT NULL,
  score INTEGER NOT NULL DEFAULT 0,
  tokens REAL NOT NULL DEFAULT 3000000,
  at REAL NOT NULL DEFAULT 0,
  win INTEGER NOT NULL DEFAULT 0,
  wcount INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (k, day, code)
);
CREATE INDEX IF NOT EXISTS ipday_day ON ipday (day);
