#!/usr/bin/env python3
import argparse
import json
import sys
import time

import schedule

from config import config
from pipeline import run_from_seed, run_single


def cmd_run(args: argparse.Namespace) -> None:
    missing = config.validate(["ANTHROPIC_API_KEY"])
    if missing:
        print(f"[오류] 필수 환경변수 누락: {', '.join(missing)}")
        print("  .env.example을 참고하여 .env 파일을 생성하세요.")
        sys.exit(1)

    platforms = args.platforms.split(",") if args.platforms else ["blogger"]

    if args.seed:
        results = run_from_seed(
            args.seed,
            top_n=args.top_n,
            platforms=platforms,
            dry_run=args.dry_run,
        )
        _print_summary(results)
    elif args.keyword:
        result = run_single(
            args.keyword,
            context=args.context or "",
            platforms=platforms,
            dry_run=args.dry_run,
        )
        _print_summary([result])
    else:
        print("[오류] --keyword 또는 --seed 중 하나를 지정하세요.")
        sys.exit(1)


def cmd_schedule(args: argparse.Namespace) -> None:
    missing = config.validate(["ANTHROPIC_API_KEY"])
    if missing:
        print(f"[오류] 필수 환경변수 누락: {', '.join(missing)}")
        sys.exit(1)

    seeds = [s.strip() for s in args.seeds.split(",")]
    platforms = args.platforms.split(",") if args.platforms else ["blogger"]

    def job():
        for seed in seeds:
            run_from_seed(seed, top_n=args.top_n, platforms=platforms)
            time.sleep(10)

    print(f"[scheduler] 매일 {args.time}에 실행 예약 (시드: {seeds})")
    schedule.every().day.at(args.time).do(job)

    while True:
        schedule.run_pending()
        time.sleep(60)


def cmd_keywords(args: argparse.Namespace) -> None:
    from modules.keyword_research import research_keywords

    result = research_keywords(args.seed, limit=args.limit)
    print(f"\n키워드 리서치 결과 ({args.seed}):")
    print("-" * 50)
    for i, kw in enumerate(result.keywords, 1):
        print(f"{i:2}. {kw.text}")
        if kw.total_searches:
            print(f"    검색량(월): PC {kw.monthly_search_pc:,} / 모바일 {kw.monthly_search_mobile:,}")
        if kw.score:
            print(f"    점수: {kw.score:.1f}")


def _print_summary(results: list) -> None:
    print("\n" + "=" * 60)
    print("파이프라인 결과 요약")
    print("=" * 60)
    for r in results:
        status = "완료" if not r.errors else f"오류 {len(r.errors)}건"
        title = r.post.title if r.post else "(생성 실패)"
        print(f"\n키워드: {r.keyword} [{status}]")
        print(f"  제목: {title}")
        for pub in r.publish_results:
            platform = pub.get("platform", "?")
            url = pub.get("url", pub.get("status", "?"))
            print(f"  발행: {platform} → {url}")
        for err in r.errors:
            print(f"  오류: {err}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="콘텐츠 자동화 파이프라인 (키워드 발굴 → AI 생성 → 멀티채널 배포)"
    )
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="파이프라인 즉시 실행")
    run_p.add_argument("--keyword", help="특정 키워드로 실행")
    run_p.add_argument("--seed", help="시드 키워드에서 자동 발굴 후 실행")
    run_p.add_argument("--top-n", type=int, default=3, help="시드에서 발굴할 키워드 수 (기본: 3)")
    run_p.add_argument("--context", help="키워드 관련 추가 컨텍스트")
    run_p.add_argument("--platforms", help="배포 플랫폼 (쉼표 구분, 예: blogger,naver)")
    run_p.add_argument("--dry-run", action="store_true", help="발행 없이 콘텐츠 생성만")

    sched_p = sub.add_parser("schedule", help="정기 자동 실행 스케줄 등록")
    sched_p.add_argument("--seeds", required=True, help="시드 키워드 목록 (쉼표 구분)")
    sched_p.add_argument("--time", default="09:00", help="실행 시각 HH:MM (기본: 09:00)")
    sched_p.add_argument("--top-n", type=int, default=3, help="키워드 수")
    sched_p.add_argument("--platforms", help="배포 플랫폼 (쉼표 구분, 예: blogger,naver)")

    kw_p = sub.add_parser("keywords", help="키워드 리서치만 실행")
    kw_p.add_argument("seed", help="시드 키워드")
    kw_p.add_argument("--limit", type=int, default=20, help="최대 키워드 수 (기본: 20)")

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "schedule":
        cmd_schedule(args)
    elif args.command == "keywords":
        cmd_keywords(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
