import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from config import config
from modules.content_generator import BlogPost, generate_blog_post
from modules.keyword_research import Keyword, research_keywords
from modules.osmu_transformer import OSMUPackage, transform
from modules.publishers.instagram import publish_to_instagram
from modules.publishers.naver import publish_to_naver
from modules.publishers.tistory import publish_to_tistory


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
    "tistory": publish_to_tistory,
    "naver": publish_to_naver,
}


def run_single(
    keyword: str,
    context: str = "",
    platforms: list[str] | None = None,
    instagram_image_url: str = "",
    dry_run: bool = False,
) -> PipelineResult:
    result = PipelineResult(keyword=keyword)
    active_platforms = platforms or ["tistory", "naver"]

    print(f"\n[pipeline] 키워드: {keyword}")

    print("[pipeline] 1/4 콘텐츠 생성 중...")
    try:
        result.post = generate_blog_post(keyword, context)
        print(f"[pipeline]   제목: {result.post.title}")
    except Exception as e:
        result.errors.append(f"content_generation: {e}")
        result.finished_at = datetime.now().isoformat()
        return result

    print("[pipeline] 2/4 OSMU 변환 중...")
    try:
        result.osmu = transform(result.post)
    except Exception as e:
        result.errors.append(f"osmu_transform: {e}")

    if dry_run:
        print("[pipeline] dry_run 모드: 발행 생략")
        result.finished_at = datetime.now().isoformat()
        return result

    print("[pipeline] 3/4 블로그 플랫폼 발행 중...")
    for platform in active_platforms:
        fn = PLATFORMS.get(platform)
        if not fn:
            result.errors.append(f"unknown_platform: {platform}")
            continue
        try:
            pub_result = fn(result.post)
            result.publish_results.append(pub_result)
            print(f"[pipeline]   {platform}: {pub_result.get('url', 'OK')}")
        except Exception as e:
            result.errors.append(f"{platform}: {e}")
            print(f"[pipeline]   {platform}: 실패 - {e}")
        time.sleep(config.POST_DELAY_SECONDS)

    if result.osmu and "instagram" in (platforms or []):
        print("[pipeline] 4/4 인스타그램 발행 중...")
        try:
            ig_result = publish_to_instagram(result.osmu, instagram_image_url)
            result.publish_results.append(ig_result)
            print(f"[pipeline]   instagram: {ig_result.get('url', 'OK')}")
        except Exception as e:
            result.errors.append(f"instagram: {e}")
            print(f"[pipeline]   instagram: 실패 - {e}")

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
