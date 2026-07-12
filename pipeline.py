from __future__ import annotations
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from config import config
from modules.content_generator import BlogPost, generate_blog_post
from modules.keyword_research import Keyword, research_keywords
from modules.osmu_transformer import OSMUPackage, transform
from modules.publishers.blogger import publish_to_blogger


@dataclass
class PipelineResult:
    keyword: str
    post: BlogPost | None = None
    osmu: OSMUPackage | None = None
    publish_results: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    finished_at: str = ""

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "title": self.post.title if self.post else "",
            "publish_results": self.publish_results,
            "errors": self.errors,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


PLATFORMS = {
    "blogger": publish_to_blogger,
}


# ---------------------------------------------------------------------------
# 내부 링크 삽입
# ---------------------------------------------------------------------------

def _load_log_posts() -> list[dict]:
    posts: list[dict] = []
    log_dir = Path("data/logs")
    if not log_dir.exists():
        return posts
    for f in sorted(log_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                posts.extend(
                    p for p in data
                    if isinstance(p, dict) and p.get("url") and p.get("title")
                )
        except Exception:
            pass
    return posts


def _ngram_overlap(a: str, b: str, n: int = 2) -> int:
    def ngrams(s: str) -> set[str]:
        s = s.lower().replace(" ", "")
        return {s[i : i + n] for i in range(len(s) - n + 1)}
    return len(ngrams(a) & ngrams(b))


def _build_links_block(posts: list[dict]) -> str:
    html = (
        '\n<div class="related-posts"'
        ' style="background:#f8f9fa;border-left:4px solid #4a90d9;padding:12px 16px;margin:20px 0">'
        '\n<p style="margin:0 0 8px;font-weight:bold">📌 관련 글</p>'
        '<ul style="margin:0;padding-left:18px">'
    )
    for p in posts:
        html += f'\n<li><a href="{p["url"]}" target="_blank" rel="noopener">{p["title"]}</a></li>'
    html += "\n</ul></div>\n"
    return html


def inject_internal_links(body_html: str, keyword: str) -> str:
    """기발행 포스트 URL을 본문 2곳(3번째·5번째 H2 앞)에 관련 글 블록으로 삽입."""
    candidates = _load_log_posts()
    if not candidates:
        return body_html

    def score(p: dict) -> int:
        return _ngram_overlap(keyword, p.get("keyword", "")) + _ngram_overlap(keyword, p.get("title", ""))

    ranked = sorted(candidates, key=score, reverse=True)
    top = [p for p in ranked if score(p) > 0]
    if not top:
        return body_html

    # 상위 6개를 앞 3개 / 뒤 3개로 나눠 두 블록에 배치
    block1 = _build_links_block(top[:3])
    block2 = _build_links_block(top[3:6] or top[:3])

    h2_pos = [m.start() for m in re.finditer(r"<h2[\s>]", body_html, re.IGNORECASE)]

    # 삽입 위치: 3번째 H2 앞 / 5번째 H2 앞 (없으면 fallback)
    insert1 = h2_pos[2] if len(h2_pos) >= 3 else (h2_pos[1] if len(h2_pos) >= 2 else None)
    insert2 = h2_pos[4] if len(h2_pos) >= 5 else (h2_pos[-1] if len(h2_pos) >= 1 else None)

    if insert1 is None:
        return body_html + block1

    # 뒤에서부터 삽입해야 앞 위치가 밀리지 않음
    if insert2 and insert2 > insert1:
        body_html = body_html[:insert2] + block2 + body_html[insert2:]
        body_html = body_html[:insert1] + block1 + body_html[insert1:]
    else:
        body_html = body_html[:insert1] + block1 + body_html[insert1:]

    return body_html


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------

def run_single(
    keyword: str,
    context: str = "",
    platforms: list[str] | None = None,
    dry_run: bool = False,
    blog_id: str = "",
    system_prompt: str | None = None,
    user_prompt_template: str | None = None,
) -> PipelineResult:
    result = PipelineResult(keyword=keyword)
    active_platforms = platforms or ["blogger"]

    print(f"\n[pipeline] 키워드: {keyword}")

    print("[pipeline] 1/3 콘텐츠 생성 중...")
    try:
        result.post = generate_blog_post(keyword, context, system_prompt, user_prompt_template)
        print(f"[pipeline]   제목: {result.post.title}")
    except Exception as e:
        result.errors.append(f"content_generation: {e}")
        result.finished_at = datetime.now().isoformat()
        return result

    print("[pipeline] 2/3 OSMU 변환 + 내부 링크 삽입 중...")
    try:
        result.osmu = transform(result.post)
    except Exception as e:
        result.errors.append(f"osmu_transform: {e}")

    result.post.body_html = inject_internal_links(result.post.body_html, keyword)

    if dry_run:
        print("[pipeline] dry_run 모드: 발행 생략")
        result.finished_at = datetime.now().isoformat()
        _save_dry_run(result)
        return result

    print("[pipeline] 3/3 블로그 플랫폼 발행 중...")
    for platform in active_platforms:
        fn = PLATFORMS.get(platform)
        if fn is None:
            if platform not in PLATFORMS:
                result.errors.append(f"unknown_platform: {platform}")
            continue
        try:
            if platform == "blogger" and blog_id:
                pub_result = fn(result.post, blog_id=blog_id)
            else:
                pub_result = fn(result.post)
            result.publish_results.append(pub_result)
            print(f"[pipeline]   {platform}: {pub_result.get('url', 'OK')}")
        except Exception as e:
            result.errors.append(f"{platform}: {e}")
            print(f"[pipeline]   {platform}: 실패 - {e}")
        time.sleep(config.POST_DELAY_SECONDS)

    result.finished_at = datetime.now().isoformat()
    _save_result(result)
    return result


def run_from_seed(
    seed: str,
    top_n: int = 3,
    platforms: list[str] | None = None,
    dry_run: bool = False,
) -> list[PipelineResult]:
    print(f"\n[pipeline] 시드 키워드로 리서치 시작: {seed}")
    research = research_keywords(seed, limit=top_n)

    keywords = research.keywords[:top_n] if research.keywords else [Keyword(text=seed)]
    print(f"[pipeline] 발굴된 키워드 {len(keywords)}개: {[k.text for k in keywords]}")

    results = []
    for kw in keywords:
        result = run_single(kw.text, platforms=platforms, dry_run=dry_run)
        results.append(result)

    return results


def _save_result(result: PipelineResult) -> None:
    log_dir = Path("data")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d')}.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")


def _save_dry_run(result: PipelineResult) -> None:
    if not result.post:
        return
    out_dir = Path("data/dry_run")
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = result.keyword.replace(" ", "_")[:40]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"{ts}_{slug}.html"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"<!-- keyword: {result.keyword} -->\n")
        f.write(f"<!-- title: {result.post.title} -->\n")
        f.write(f"<!-- meta: {result.post.meta_description} -->\n")
        f.write(f"<!-- tags: {', '.join(result.post.tags)} -->\n\n")
        f.write(result.post.body_html)
    print(f"[pipeline] 콘텐츠 저장됨: {out_file}")
