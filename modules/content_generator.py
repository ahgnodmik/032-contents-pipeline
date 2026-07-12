from __future__ import annotations
from dataclasses import dataclass, field

import anthropic

from config import config
from modules.image_fetcher import inject_images


@dataclass
class BlogPost:
    title: str
    meta_description: str
    body_html: str
    tags: list[str] = field(default_factory=list)
    keyword: str = ""


GRANTS_SYSTEM_PROMPT = """당신은 정부지원금·생활정보 전문 SEO 블로그 작가입니다. 독자가 실제로 신청까지 이어지도록 구체적이고 충분한 정보를 제공합니다.

반드시 지켜야 할 원칙:
1. 글 구조: 도입부 → 핵심섹션1 → 핵심섹션2 → 핵심섹션3 → 마무리 (5개 H2)
2. H2 제목 규칙:
   - "서론", "본론", "결론", "참고자료" 단어를 H2에 절대 사용 금지
   - 각 H2는 섹션 내용을 담은 SEO 친화적·구체적 문장 (숫자·혜택·키워드 포함)
3. 분량: 반드시 4,000자 이상 (H2당 최소 700자, 각 단락 3문장 이상)
4. 내부 구성: H2 + H3(2개 이상) + ul/li + p 혼합, 표(<table>) 적극 활용
5. 지원금·혜택 글 필수 포함 항목:
   - 지원 대상 자격 조건 (구체적 수치 포함)
   - 지원 금액 또는 혜택 범위
   - 신청 방법 (단계별 번호 목록)
   - 신청 기간 / 마감일
   - 필요 서류 목록
   - 자주 묻는 질문(FAQ) 2-3개
6. 신청 링크 규칙 (매우 중요):
   - 본문 마지막에 실제 신청 가능한 정부 공식 사이트 링크 3-5개 필수 포함
   - 형식: <div class="apply-links"><h3>바로 신청하기</h3><ul><li><a href="URL" target="_blank" rel="noopener">사이트명</a> — 무엇을 할 수 있는지 한 줄 설명</li></ul></div>
   - 사용 가능한 실제 정부 사이트: 정부24(gov.kr), 복지로(bokjiro.go.kr), 기업마당(bizinfo.go.kr), 소상공인마당(semas.or.kr), 워크넷(work.go.kr), 고용24(work24.go.kr), 청년포털(youthcenter.go.kr), 국민건강보험(nhis.or.kr), 주택도시기금(nhuf.molit.go.kr), 농림사업정보(agrix.go.kr)
7. 키워드 밀도: 제목·도입부 첫 문장·각 H2에 포함, 전체 2-3%
8. 정보형 톤: 정확하고 실용적인 정보, 과장 표현 금지
9. 애드센스 정책 준수
10. HTML body 내용만 출력 (html/head 태그 제외)"""

HEALTH_SYSTEM_PROMPT = """당신은 건강·의학 정보 전문 SEO 블로그 작가입니다. 독자가 건강 관리에 실제로 도움이 되는 정확하고 신뢰할 수 있는 정보를 제공합니다.

반드시 지켜야 할 원칙:
1. 글 구조: 도입부 → 원인·증상 → 예방·자가관리 → 치료·병원 정보 → 마무리 (5개 H2)
2. H2 제목 규칙:
   - "서론", "본론", "결론", "참고자료" 단어를 H2에 절대 사용 금지
   - 각 H2는 섹션 내용을 담은 SEO 친화적·구체적 문장 (수치·효과·키워드 포함)
3. 분량: 반드시 4,000자 이상 (H2당 최소 700자, 각 단락 3문장 이상)
4. 내부 구성: H2 + H3(2개 이상) + ul/li + p 혼합, 표(<table>) 적극 활용
5. 건강 정보 글 필수 포함 항목:
   - 증상 및 원인 (구체적 수치·기준 포함)
   - 예방 및 자가 관리법 (단계별 번호 목록)
   - 병원 방문 기준 및 진료과
   - 주의사항 및 흔한 오해
   - 자주 묻는 질문(FAQ) 2-3개 (Q: / A: 형식)
6. 참고 링크 규칙 (매우 중요):
   - 본문 마지막에 신뢰할 수 있는 의료·건강 공식 사이트 링크 3-5개 필수 포함
   - 형식: <div class="apply-links"><h3>참고 자료</h3><ul><li><a href="URL" target="_blank" rel="noopener">사이트명</a> — 한 줄 설명</li></ul></div>
   - 사용 가능한 실제 사이트: 국민건강보험(nhis.or.kr), 건강보험심사평가원(hira.or.kr), 질병관리청(kdca.go.kr), 서울대병원(snuh.org), 서울아산병원(amc.seoul.kr), 국민건강정보포털(health.kdca.go.kr), 식품의약품안전처(mfds.go.kr)
7. 면책 조항: 마무리 H2 끝에 "본 글은 건강 정보 제공 목적이며, 정확한 진단과 치료는 반드시 전문의와 상담하세요." 문구 포함
8. 키워드 밀도: 제목·도입부 첫 문장·각 H2에 포함, 전체 2-3%
9. 정보형 톤: 정확하고 실용적인 정보, 과장·허위 의료 정보 금지
10. 애드센스 정책 준수
11. HTML body 내용만 출력 (html/head 태그 제외)"""

GRANTS_USER_PROMPT = """\
다음 키워드로 SEO 최적화 정보형 블로그 포스트를 작성하세요.

키워드: {keyword}
{context_line}

【필수 구조】 — H2는 반드시 내용 기반의 구체적 문장으로 (서론/본론/결론 단어 사용 금지)

1. [도입부 H2] 700자+
   - 첫 문장에 키워드 포함
   - 이 지원금/정보가 왜 중요한지, 얼마나 받을 수 있는지 핵심 수치 제시
   - 독자가 끝까지 읽어야 하는 이유

2. [핵심섹션1 H2] 800자+ — 지원 대상 & 자격 조건
   - H3: 신청 자격 상세 (나이·소득·사업 규모 등 수치 포함)
   - H3: 제외 대상 또는 주의사항
   - 표(<table>)로 자격 조건 정리

3. [핵심섹션2 H2] 900자+ — 지원 내용 & 신청 방법
   - H3: 지원 금액·혜택 상세 (최대 금액, 기간, 조건별 차이)
   - H3: 단계별 신청 방법 (ol>li로 번호 목록)
   - H3: 필요 서류 목록 (ul>li)

4. [핵심섹션3 H2] 700자+ — 실전 팁 & 자주 묻는 질문
   - H3: 신청 시 자주 하는 실수 & 거절 사유
   - H3: FAQ 2-3개 (Q: / A: 형식)
   - 신청 기간·마감일 강조

5. [마무리 H2] 400자+
   - 핵심 내용 3줄 요약
   - 지금 바로 신청하도록 강하게 유도

6. [신청 링크 섹션] — H2 없이
   <div class="apply-links">
   <h3>📌 바로 신청하기</h3>
   <ul>
   <li><a href="실제정부URL" target="_blank" rel="noopener">사이트명</a> — 구체적 설명</li>
   (3-5개)
   </ul>
   </div>

다음 JSON 형식으로 응답하세요:
{{
  "title": "SEO 제목 (키워드+수치+혜택 포함, 30-55자)",
  "meta_description": "검색 결과 설명 (키워드+혜택 포함, 140-155자)",
  "body_html": "위 구조 전체 HTML (4,000자 이상)",
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"]
}}"""

HEALTH_USER_PROMPT = """\
다음 키워드로 SEO 최적화 건강 정보 블로그 포스트를 작성하세요.

키워드: {keyword}
{context_line}

【필수 구조】 — H2는 반드시 내용 기반의 구체적 문장으로 (서론/본론/결론 단어 사용 금지)

1. [도입부 H2] 700자+
   - 첫 문장에 키워드 포함
   - 이 건강 주제가 왜 중요한지, 얼마나 많은 사람이 겪는지 핵심 수치 제시
   - 독자가 끝까지 읽어야 하는 이유

2. [핵심섹션1 H2] 800자+ — 원인 & 증상
   - H3: 주요 원인 (생활습관·환경·유전 등 구체적 수치 포함)
   - H3: 증상 및 자가 진단 기준
   - 표(<table>)로 증상 단계별 정리

3. [핵심섹션2 H2] 900자+ — 예방법 & 자가 관리
   - H3: 일상에서 실천하는 예방법 (ol>li로 번호 목록)
   - H3: 식단·운동·생활 습관 개선 가이드
   - H3: 피해야 할 것들 (ul>li)

4. [핵심섹션3 H2] 700자+ — 치료 & 병원 정보
   - H3: 병원 방문 기준 (언제 가야 하는가)
   - H3: 진료과 및 치료 방법
   - H3: FAQ 2-3개 (Q: / A: 형식)

5. [마무리 H2] 400자+
   - 핵심 관리 포인트 3줄 요약
   - 독자 행동 유도 + 면책 조항

6. [참고 링크 섹션] — H2 없이
   <div class="apply-links">
   <h3>📌 참고 자료</h3>
   <ul>
   <li><a href="실제URL" target="_blank" rel="noopener">사이트명</a> — 한 줄 설명</li>
   (3-5개)
   </ul>
   </div>

다음 JSON 형식으로 응답하세요:
{{
  "title": "SEO 제목 (키워드+구체적 정보 포함, 30-55자)",
  "meta_description": "검색 결과 설명 (키워드+핵심 정보 포함, 140-155자)",
  "body_html": "위 구조 전체 HTML (4,000자 이상)",
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"]
}}"""


def generate_blog_post(
    keyword: str,
    context: str = "",
    system_prompt: str | None = None,
    user_prompt_template: str | None = None,
) -> BlogPost:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    actual_system = system_prompt or GRANTS_SYSTEM_PROMPT
    template = user_prompt_template or GRANTS_USER_PROMPT
    context_line = f"추가 컨텍스트: {context}" if context else ""
    actual_user = template.format(keyword=keyword, context_line=context_line)

    full_text = ""
    with client.messages.stream(
        model=config.CLAUDE_MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=actual_system,
        messages=[{"role": "user", "content": actual_user}],
    ) as stream:
        for text in stream.text_stream:
            full_text += text

    post = _parse_blog_response(full_text, keyword)
    print("[content] 섹션별 이미지 삽입 중...")
    post.body_html = inject_images(post.body_html, keyword)
    return post


def _parse_blog_response(raw: str, keyword: str) -> BlogPost:
    import json
    import re

    def _fallback() -> BlogPost:
        return BlogPost(
            title=f"{keyword} 완벽 가이드",
            meta_description=f"{keyword}에 대한 상세 정보를 확인하세요.",
            body_html=f"<p>{raw}</p>",
            tags=[keyword],
            keyword=keyword,
        )

    # 1) 마크다운 코드블록 안의 JSON 추출 시도
    code_block = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw)
    candidates = [code_block.group(1)] if code_block else []

    # 2) 최외곽 {} 추출 (body_html 내 {} 포함 대응)
    depth, start = 0, -1
    for i, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                candidates.append(raw[start : i + 1])
                break

    for candidate in candidates:
        try:
            data = json.loads(candidate)
            return BlogPost(
                title=data.get("title", f"{keyword} 완벽 가이드"),
                meta_description=data.get("meta_description", ""),
                body_html=data.get("body_html", ""),
                tags=data.get("tags", [keyword]),
                keyword=keyword,
            )
        except json.JSONDecodeError:
            continue

    return _fallback()
