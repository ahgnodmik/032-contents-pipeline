import re
from dataclasses import dataclass

import anthropic

from config import config
from modules.content_generator import BlogPost


@dataclass
class OSMUPackage:
    blog_post: BlogPost
    instagram_caption: str = ""
    naver_intro: str = ""
    kakao_summary: str = ""


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


def _call_claude(prompt: str, max_tokens: int = 1000) -> str:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in message.content:
        if block.type == "text":
            return block.text
    return ""


def to_instagram_caption(post: BlogPost) -> str:
    plain_body = _strip_html(post.body_html)[:500]
    hashtags = " ".join(f"#{tag.replace(' ', '')}" for tag in post.tags[:10])

    prompt = f"""다음 블로그 포스트를 인스타그램 캡션으로 변환해주세요.

제목: {post.title}
본문 요약: {plain_body}

요구사항:
- 2200자 이내
- 핵심 내용을 감성적이고 공감가는 문체로
- 줄바꿈을 활용한 가독성
- 마지막에 해시태그 포함: {hashtags}
- 팔로워가 프로필 링크를 클릭하도록 유도하는 CTA 포함

캡션만 출력하세요 (설명 없이)."""

    return _call_claude(prompt, max_tokens=1200)


def to_naver_intro(post: BlogPost) -> str:
    prompt = f"""다음 블로그 포스트의 네이버 블로그용 도입부를 작성해주세요.

제목: {post.title}
키워드: {post.keyword}

요구사항:
- 200-300자 분량의 친근한 도입부
- 네이버 블로그 특성상 구어체, 공감 유발
- 독자가 계속 읽고 싶게 만드는 훅
- 텍스트만 출력 (HTML 없이)

도입부만 출력하세요."""

    return _call_claude(prompt, max_tokens=500)


def to_kakao_summary(post: BlogPost) -> str:
    plain_body = _strip_html(post.body_html)[:800]
    prompt = f"""다음 블로그 포스트를 카카오채널/티스토리용 요약으로 변환해주세요.

제목: {post.title}
본문: {plain_body}

요구사항:
- 핵심 내용 3-5가지 bullet point 형식
- 각 포인트는 한 줄로 간결하게
- 텍스트만 출력

요약만 출력하세요."""

    return _call_claude(prompt, max_tokens=500)


def transform(post: BlogPost) -> OSMUPackage:
    pkg = OSMUPackage(blog_post=post)
    pkg.instagram_caption = to_instagram_caption(post)
    pkg.naver_intro = to_naver_intro(post)
    pkg.kakao_summary = to_kakao_summary(post)
    return pkg
