"""일일 자동 발행 — BlogProfile 기반 범용 러너.

각 블로그(지원금 / 건강 등)는 BlogProfile 인스턴스를 정의하고
run_profile(profile) 을 호출합니다.

로테이션 규칙:
  1. group_index 그룹에서 seed 선택 → 키워드 리서치 → 조건 통과 시 발행
  2. 발행 성공 시 group_index를 다음 그룹으로 전진
  3. 시드는 14일 쿨다운 (SEED_COOLDOWN_DAYS)
  4. 최근 14일 발행 키워드와 Jaccard 유사도 0.55 이상이면 차단
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

from modules.keyword_research import research_keywords
from pipeline import run_single

SEED_COOLDOWN_DAYS = 14
KEYWORD_COOLDOWN_DAYS = 14
NGRAM_BLOCK_THRESHOLD = 0.55


# ---------------------------------------------------------------------------
# BlogProfile
# ---------------------------------------------------------------------------

@dataclass
class BlogProfile:
    name: str                          # 표시용 이름
    blog_id: str                       # Blogger Blog ID
    seeds_file: Path                   # 시드 키워드 파일
    published_file: Path               # 발행 이력 JSON
    rotation_file: Path                # 로테이션 상태 JSON
    log_dir: Path                      # 일별 로그 디렉터리
    system_prompt: str | None = None   # None → GRANTS_SYSTEM_PROMPT
    user_prompt_template: str | None = None  # None → GRANTS_USER_PROMPT


# ---------------------------------------------------------------------------
# 유사도
# ---------------------------------------------------------------------------

def _ngrams(text: str, n: int = 2) -> set[str]:
    s = text.lower().replace(" ", "")
    return {s[i : i + n] for i in range(len(s) - n + 1)} if len(s) >= n else set()


def _jaccard(a: str, b: str) -> float:
    ga, gb = _ngrams(a), _ngrams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def _is_too_similar(keyword: str, recent: list[str]) -> bool:
    return any(_jaccard(keyword, r) >= NGRAM_BLOCK_THRESHOLD for r in recent)


# ---------------------------------------------------------------------------
# 데이터 로드 / 저장
# ---------------------------------------------------------------------------

def _parse_seed_groups(seeds_file: Path) -> dict[str, list[str]]:
    if not seeds_file.exists():
        return {}
    groups: dict[str, list[str]] = {}
    current = "기타"
    for raw in seeds_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"#\s*\[(.+?)\]", line)
        if m:
            current = m.group(1)
            groups.setdefault(current, [])
        elif not line.startswith("#"):
            groups.setdefault(current, []).append(line)
    return {k: v for k, v in groups.items() if v}


def _load_published(path: Path) -> set[str]:
    if path.exists():
        return set(json.loads(path.read_text(encoding="utf-8")))
    return set()


def _save_published(path: Path, published: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(published), ensure_ascii=False, indent=2), encoding="utf-8")


def _load_rotation(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"group_index": 0, "seed_last_used": {}}


def _save_rotation(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_recent_keywords(log_dir: Path) -> list[str]:
    cutoff = date.today() - timedelta(days=KEYWORD_COOLDOWN_DAYS)
    keywords: list[str] = []
    for f in sorted(log_dir.glob("*.json")):
        try:
            entries = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                continue
            for e in entries:
                ds = e.get("published_at", "")[:10]
                if ds and date.fromisoformat(ds) >= cutoff and e.get("keyword"):
                    keywords.append(e["keyword"])
        except Exception:
            pass
    return keywords


def _append_log(log_file: Path, entry: dict) -> None:
    existing = json.loads(log_file.read_text(encoding="utf-8")) if log_file.exists() else []
    log_file.write_text(
        json.dumps(existing + [entry], ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# 키워드 선택
# ---------------------------------------------------------------------------

def _pick_from_seed(seed: str, published: set[str], recent: list[str]) -> tuple[str, int] | None:
    try:
        result = research_keywords(seed, limit=20)
    except Exception as e:
        print(f"[rotation]   리서치 실패 ({seed}): {e}")
        return None
    for kw in result.keywords:
        if kw.text in published:
            continue
        if _is_too_similar(kw.text, recent):
            print(f"[rotation]   유사 스킵: {kw.text}")
            continue
        return kw.text, kw.total_searches
    return None


def _select_keyword(
    groups: dict[str, list[str]],
    state: dict,
    published: set[str],
    recent: list[str],
) -> tuple[str, int, str, str] | None:
    group_names = list(groups.keys())
    n = len(group_names)
    start = state.get("group_index", 0) % n
    seed_last_used: dict[str, str] = state.get("seed_last_used", {})
    cooldown_cutoff = (date.today() - timedelta(days=SEED_COOLDOWN_DAYS)).isoformat()

    for offset in range(n):
        g_idx = (start + offset) % n
        gname = group_names[g_idx]
        seeds = groups[gname]

        available = sorted(
            seeds,
            key=lambda s: (
                0 if seed_last_used.get(s, "0000-00-00") <= cooldown_cutoff else 1,
                seed_last_used.get(s, "0000-00-00"),
            ),
        )

        print(f"[rotation] 그룹 '{gname}' — 시드 {len(available)}개 탐색")
        for seed in available:
            last = seed_last_used.get(seed, "없음")
            print(f"[rotation]   시드 '{seed}' (마지막 사용: {last})")
            pick = _pick_from_seed(seed, published, recent)
            if pick:
                keyword, searches = pick
                state["group_index"] = (g_idx + 1) % n
                return keyword, searches, seed, gname

    return None


# ---------------------------------------------------------------------------
# 범용 실행
# ---------------------------------------------------------------------------

def run_profile(profile: BlogProfile) -> None:
    groups = _parse_seed_groups(profile.seeds_file)
    if not groups:
        print(f"[{profile.name}] {profile.seeds_file} 에 시드 키워드를 추가하세요.")
        return

    published = _load_published(profile.published_file)
    recent = _load_recent_keywords(profile.log_dir)
    state = _load_rotation(profile.rotation_file)
    today = date.today().isoformat()
    profile.log_dir.mkdir(parents=True, exist_ok=True)
    log_file = profile.log_dir / f"{today}.json"

    group_names = list(groups.keys())
    cur_group = group_names[state.get("group_index", 0) % len(group_names)]
    print(f"\n{'='*55}")
    print(f"[{profile.name}] {today}  현재 그룹: {cur_group}")
    print(f"[{profile.name}] 발행 이력: {len(published)}개  최근 유사 차단: {len(recent)}개")
    print(f"{'='*55}\n")

    selection = _select_keyword(groups, state, published, recent)
    if not selection:
        print(f"[{profile.name}] 발행 가능한 키워드 없음")
        return

    keyword, monthly_searches, seed, group = selection
    print(f"\n[{profile.name}] 선택 키워드: '{keyword}'")
    print(f"[{profile.name}]   그룹: {group} / 시드: {seed} / 월검색: {monthly_searches:,}\n")

    try:
        result = run_single(
            keyword,
            platforms=["blogger"],
            blog_id=profile.blog_id,
            system_prompt=profile.system_prompt,
            user_prompt_template=profile.user_prompt_template,
        )
    except Exception as e:
        print(f"[{profile.name}] 실행 예외: {e}")
        return

    if result.errors or not result.post:
        print(f"[{profile.name}] 발행 실패: {result.errors}")
        return

    url = next((r.get("url", "") for r in result.publish_results), "")

    published.add(keyword)
    state.setdefault("seed_last_used", {})[seed] = today
    _save_published(profile.published_file, published)
    _save_rotation(profile.rotation_file, state)

    _append_log(log_file, {
        "seed": seed,
        "group": group,
        "keyword": keyword,
        "title": result.post.title,
        "url": url,
        "monthly_searches": monthly_searches,
        "published_at": datetime.now().isoformat(),
    })

    print(f"\n{'='*55}")
    print(f"[{profile.name}] 완료: {result.post.title}")
    print(f"[{profile.name}] URL : {url}")
    print(f"[{profile.name}] 다음 그룹: {group_names[state['group_index']]}")
    print(f"{'='*55}\n")


# ---------------------------------------------------------------------------
# 지원금 블로그 프로필 (기본)
# ---------------------------------------------------------------------------

GRANTS_PROFILE = BlogProfile(
    name="지원금블로그",
    blog_id="",  # config.BLOGGER_BLOG_ID 사용
    seeds_file=Path("data/seed_keywords.txt"),
    published_file=Path("data/published_keywords.json"),
    rotation_file=Path("data/rotation_state.json"),
    log_dir=Path("data/logs"),
)


def daily_run() -> None:
    from config import config
    from modules.content_generator import GRANTS_SYSTEM_PROMPT, GRANTS_USER_PROMPT
    profile = BlogProfile(
        name=GRANTS_PROFILE.name,
        blog_id=config.BLOGGER_BLOG_ID,
        seeds_file=GRANTS_PROFILE.seeds_file,
        published_file=GRANTS_PROFILE.published_file,
        rotation_file=GRANTS_PROFILE.rotation_file,
        log_dir=GRANTS_PROFILE.log_dir,
        system_prompt=GRANTS_SYSTEM_PROMPT,
        user_prompt_template=GRANTS_USER_PROMPT,
    )
    run_profile(profile)


if __name__ == "__main__":
    daily_run()
