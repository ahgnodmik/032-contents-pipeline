import requests

from config import config
from modules.content_generator import BlogPost


class TistoryPublisher:
    BASE_URL = "https://www.tistory.com/apis"

    def _params(self, extra: dict | None = None) -> dict:
        params = {
            "access_token": config.TISTORY_ACCESS_TOKEN,
            "blogName": config.TISTORY_BLOG_NAME,
            "output": "json",
        }
        if extra:
            params.update(extra)
        return params

    def post(self, post: BlogPost, category_id: str = "") -> dict:
        url = f"{self.BASE_URL}/post/write"
        params = self._params(
            {
                "title": post.title,
                "content": post.body_html,
                "visibility": "3",
                "tag": ",".join(post.tags[:10]),
                "categoryId": category_id,
            }
        )
        resp = requests.post(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return {
            "platform": "tistory",
            "post_id": data.get("tistory", {}).get("postId", ""),
            "url": data.get("tistory", {}).get("url", ""),
        }

    def list_categories(self) -> list[dict]:
        url = f"{self.BASE_URL}/category/list"
        resp = requests.get(url, params=self._params(), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("tistory", {}).get("item", {}).get("categories", [])


def publish_to_tistory(post: BlogPost, category_id: str = "") -> dict:
    publisher = TistoryPublisher()
    return publisher.post(post, category_id)
