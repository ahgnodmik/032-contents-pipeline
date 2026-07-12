"""Pexels API로 키워드 관련 정사각형 이미지를 가져와 HTML 섹션에 삽입."""
from __future__ import annotations

import re
import time

import requests

from config import config

PEXELS_API = "https://api.pexels.com/v1/search"

_cache: dict[str, str] = {}


def fetch_square_image(keyword: str) -> tuple[str, str]:
    """키워드로 Pexels 정사각형 이미지 URL과 alt 텍스트를 반환. 실패 시 ('', '')."""
    if not config.PEXELS_API_KEY:
        return "", ""

    if keyword in _cache:
        return _cache[keyword], keyword

    try:
        resp = requests.get(
            PEXELS_API,
            headers={"Authorization": config.PEXELS_API_KEY},
            params={"query": keyword, "per_page": 3, "orientation": "square", "locale": "ko-KR"},
            timeout=8,
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            # 한국어 검색 실패 시 영어로 재시도
            resp2 = requests.get(
                PEXELS_API,
                headers={"Authorization": config.PEXELS_API_KEY},
                params={"query": keyword, "per_page": 3, "orientation": "square"},
                timeout=8,
            )
            resp2.raise_for_status()
            photos = resp2.json().get("photos", [])

        if not photos:
            return "", ""

        photo = photos[0]
        url = photo["src"]["large"]  # large: ~940px 정방형 크롭
        alt = photo.get("alt", keyword)
        _cache[keyword] = url
        return url, alt

    except Exception as e:
        print(f"[image] '{keyword}' 이미지 조회 실패: {e}")
        return "", ""


def _img_html(url: str, alt: str) -> str:
    return (
        f'<div style="text-align:center;margin:24px 0;">'
        f'<img src="{url}" alt="{alt}" '
        f'style="width:100%;max-width:560px;aspect-ratio:1/1;object-fit:cover;'
        f'border-radius:8px;display:inline-block;">'
        f'</div>'
    )


def _fetch_photo_pool(keyword: str, count: int = 15) -> list[dict]:
    """키워드로 Pexels 이미지 풀을 한 번에 가져옴."""
    if not config.PEXELS_API_KEY:
        return []
    try:
        resp = requests.get(
            PEXELS_API,
            headers={"Authorization": config.PEXELS_API_KEY},
            params={"query": keyword, "per_page": count, "orientation": "square"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("photos", [])
    except Exception as e:
        print(f"[image] '{keyword}' 풀 조회 실패: {e}")
        return []


def _section_keyword(h2_plain: str, seed: str) -> str:
    """H2 텍스트에서 시드와 다른 구분 단어를 뽑아 검색어 생성."""
    clean = re.sub(r"[^\w\s가-힣a-zA-Z]", " ", h2_plain).strip()
    words = [w for w in clean.split() if w not in ("및", "의", "와", "과", "을", "를", "이", "가", "은", "는")]
    # 시드 키워드 단어 제거 후 앞 단어 + 시드 조합
    seed_words = set(seed.split())
    unique = [w for w in words if w not in seed_words]
    if unique:
        return f"{seed} {unique[0]}" if len(unique) < 3 else " ".join(unique[:3])
    return seed


def inject_images(body_html: str, seed_keyword: str) -> str:
    """각 H2 섹션 끝에 관련 정사각형 이미지를 삽입한 HTML 반환."""
    if not config.PEXELS_API_KEY:
        return body_html

    pattern = re.compile(r"(<h2[^>]*>)(.*?)(</h2>)", re.IGNORECASE | re.DOTALL)
    sections = pattern.split(body_html)

    if len(sections) <= 1:
        return body_html

    # 섹션 수 파악 → 시드 키워드로 이미지 풀 확보 (섹션 수 × 2 여유분)
    section_count = (len(sections) - 1) // 4
    pool = _fetch_photo_pool(seed_keyword, count=min(section_count * 3, 15))
    used_ids: set[int] = set()

    def _pick_photo(keyword: str, idx: int) -> tuple[str, str]:
        # 풀에서 미사용 이미지 순서대로 선택
        for photo in pool:
            if photo["id"] not in used_ids:
                used_ids.add(photo["id"])
                return photo["src"]["large"], photo.get("alt", keyword)
        # 풀 소진 시 섹션별 키워드로 개별 검색
        url, alt = fetch_square_image(f"{keyword} {idx}")
        return url, alt

    result = [sections[0]]
    i = 1
    sec_idx = 0
    while i + 3 < len(sections):
        open_tag  = sections[i]
        title_text = sections[i + 1]
        close_tag  = sections[i + 2]
        content    = sections[i + 3]

        result.append(open_tag + title_text + close_tag)

        plain_title = re.sub(r"<[^>]+>", "", title_text).strip()
        kw = _section_keyword(plain_title, seed_keyword)
        img_url, img_alt = _pick_photo(kw, sec_idx)
        sec_idx += 1
        time.sleep(0.2)

        if img_url:
            result.append(content + _img_html(img_url, img_alt))
        else:
            result.append(content)

        i += 4

    return "".join(result)
