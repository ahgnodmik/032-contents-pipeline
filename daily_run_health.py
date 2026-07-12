"""건강 블로그 일일 자동 발행.

LaunchAgent: 10:00 / 21:00 하루 2회 실행
Blog ID: 9117411480882444840 (https://www.blogger.com/blog/posts/9117411480882444840)
"""
from pathlib import Path

from config import config
from daily_run import BlogProfile, run_profile
from modules.content_generator import HEALTH_SYSTEM_PROMPT, HEALTH_USER_PROMPT

HEALTH_PROFILE = BlogProfile(
    name="건강블로그",
    blog_id=config.HEALTH_BLOGGER_BLOG_ID,
    seeds_file=Path("data/health_seed_keywords.txt"),
    published_file=Path("data/health_published_keywords.json"),
    rotation_file=Path("data/health_rotation_state.json"),
    log_dir=Path("data/health_logs"),
    system_prompt=HEALTH_SYSTEM_PROMPT,
    user_prompt_template=HEALTH_USER_PROMPT,
)

if __name__ == "__main__":
    run_profile(HEALTH_PROFILE)
