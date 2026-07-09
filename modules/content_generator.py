from dataclasses import dataclass, field

import anthropic

from config import config


@dataclass
class BlogPost:
    title: str
    meta_description: str
    body_html: str
    tags: list[str] = field(default_factory=list)
    keyword: str = ""


BLOG_SYSTEM_PROMPT = """당신은 구글 애드센스 승인을 목표로 하는 SEO 최적화 블로그 포스트 전문 작가입니다.
다음 원칙을 반드시 따르세요:
- 독자에게 진짜 가치 있는 정보를 제공하는 고품질 콘텐츠
- 자연스러운 키워드 밀도 (2-3%)
- 명확한 H2/H3 구조로 가독성 확보
- 최소 1,500자 이상의 충분한 분량
- 애드센스 정책 준수 (성인/도박/폭력 콘텐츠 금지)
- HTML 형식으로 출력 (body 내용만, html/head 태그 제외)"""


def generate_blog_post(keyword: str, context: str = "") -> BlogPost:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    user_prompt = f"""다음 키워드를 중심으로 SEO 최적화 블로그 포스트를 작성해주세요.

키워드: {keyword}
{f"추가 컨텍스트: {context}" if context else ""}

다음 JSON 형식으로 응답하세요:
{{
  "title": "SEO 최적화된 제목 (50-60자)",
  "meta_description": "검색 결과에 표시될 설명 (150-160자)",
  "body_html": "본문 HTML (H2, H3, p, ul, li 태그 사용, 최소 1500자)",
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"]
}}"""

    full_text = ""
    with client.messages.stream(
        model=config.CLAUDE_MODEL,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        system=BLOG_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        for text in stream.text_stream:
            full_text += text

    return _parse_blog_response(full_text, keyword)


def _parse_blog_response(raw: str, keyword: str) -> BlogPost:
    import json
    import re

    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return BlogPost(
            title=f"{keyword} 완벽 가이드",
            meta_description=f"{keyword}에 대한 상세 정보를 확인하세요.",
            body_html=f"<p>{raw}</p>",
            tags=[keyword],
            keyword=keyword,
        )

    try:
        data = json.loads(match.group())
        return BlogPost(
            title=data.get("title", f"{keyword} 완벽 가이드"),
            meta_description=data.get("meta_description", ""),
            body_html=data.get("body_html", ""),
            tags=data.get("tags", [keyword]),
            keyword=keyword,
        )
    except json.JSONDecodeError:
        return BlogPost(
            title=f"{keyword} 완벽 가이드",
            meta_description=f"{keyword}에 대한 상세 정보를 확인하세요.",
            body_html=f"<p>{raw}</p>",
            tags=[keyword],
            keyword=keyword,
        )
