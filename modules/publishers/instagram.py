import time

import requests

from config import config
from modules.osmu_transformer import OSMUPackage


class InstagramPublisher:
    GRAPH_API_BASE = "https://graph.facebook.com/v19.0"

    def _url(self, path: str) -> str:
        return f"{self.GRAPH_API_BASE}/{path}"

    def create_text_container(self, caption: str) -> str:
        resp = requests.post(
            self._url(f"{config.INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"),
            params={
                "media_type": "REELS",
                "caption": caption,
                "access_token": config.INSTAGRAM_ACCESS_TOKEN,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def create_image_container(self, image_url: str, caption: str) -> str:
        resp = requests.post(
            self._url(f"{config.INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"),
            params={
                "image_url": image_url,
                "caption": caption,
                "access_token": config.INSTAGRAM_ACCESS_TOKEN,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def publish_container(self, container_id: str) -> dict:
        self._wait_for_container(container_id)
        resp = requests.post(
            self._url(f"{config.INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish"),
            params={
                "creation_id": container_id,
                "access_token": config.INSTAGRAM_ACCESS_TOKEN,
            },
            timeout=15,
        )
        resp.raise_for_status()
        media_id = resp.json()["id"]
        return {
            "platform": "instagram",
            "media_id": media_id,
            "url": f"https://www.instagram.com/p/{media_id}/",
        }

    def _wait_for_container(self, container_id: str, retries: int = 5) -> None:
        for _ in range(retries):
            resp = requests.get(
                self._url(container_id),
                params={
                    "fields": "status_code",
                    "access_token": config.INSTAGRAM_ACCESS_TOKEN,
                },
                timeout=10,
            )
            status = resp.json().get("status_code", "")
            if status == "FINISHED":
                return
            time.sleep(3)
        raise TimeoutError(f"Instagram 컨테이너 {container_id} 처리 시간 초과")

    def post(self, pkg: OSMUPackage, image_url: str = "") -> dict:
        caption = pkg.instagram_caption
        if image_url:
            container_id = self.create_image_container(image_url, caption)
        else:
            container_id = self.create_text_container(caption)
        return self.publish_container(container_id)


def publish_to_instagram(pkg: OSMUPackage, image_url: str = "") -> dict:
    publisher = InstagramPublisher()
    return publisher.post(pkg, image_url)
