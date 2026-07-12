from __future__ import annotations

import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import config
from modules.content_generator import BlogPost

SCOPES = ["https://www.googleapis.com/auth/blogger"]
CREDENTIALS_FILE = Path("credentials.json")
TOKEN_FILE = Path("data/blogger_token.json")


def _get_credentials() -> Credentials:
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    "credentials.json 파일이 없습니다.\n"
                    "Google Cloud Console → API 및 서비스 → 사용자 인증 정보 →\n"
                    "OAuth 2.0 클라이언트 ID (데스크톱 앱) 생성 후 credentials.json을\n"
                    "프로젝트 루트에 저장하세요."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return creds


def publish_to_blogger(post: BlogPost, blog_id: str = "") -> dict:
    blog_id = blog_id or config.BLOGGER_BLOG_ID
    if not blog_id:
        raise RuntimeError("BLOGGER_BLOG_ID가 .env에 설정되지 않았습니다.")

    creds = _get_credentials()
    service = build("blogger", "v3", credentials=creds)

    body = {
        "title": post.title,
        "content": post.body_html,
        "labels": post.tags[:10],
    }

    result = service.posts().insert(blogId=blog_id, body=body, isDraft=False).execute()

    url = result.get("url", "")
    print(f"[blogger] 발행 완료: {url}")
    return {"platform": "blogger", "url": url, "title": post.title}
