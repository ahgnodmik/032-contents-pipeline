#!/bin/bash
# 스케줄러 등록/해제 스크립트

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

_install() {
  local plist="$1" label="$2" log_dir="$3"
  mkdir -p "$log_dir"
  cp "$SCRIPT_DIR/$plist" "$HOME/Library/LaunchAgents/$plist"
  launchctl load "$HOME/Library/LaunchAgents/$plist"
  echo "✅ [$label] 등록 완료 — 로그: $log_dir/launchd_stdout.log"
}

_uninstall() {
  local plist="$1" label="$2"
  launchctl unload "$HOME/Library/LaunchAgents/$plist" 2>/dev/null
  rm -f "$HOME/Library/LaunchAgents/$plist"
  echo "✅ [$label] 해제 완료"
}

case "$1" in
  install)
    _install "com.contents-pipeline.daily.plist"  "지원금블로그" "$PROJECT_DIR/data/logs"
    _install "com.contents-pipeline.health.plist" "건강블로그"   "$PROJECT_DIR/data/health_logs"
    echo ""
    echo "📅 스케줄:"
    echo "   지원금블로그: 08:00 / 19:00"
    echo "   건강블로그:   10:00 / 21:00"
    ;;
  uninstall)
    _uninstall "com.contents-pipeline.daily.plist"  "지원금블로그"
    _uninstall "com.contents-pipeline.health.plist" "건강블로그"
    ;;
  status)
    echo "=== 등록된 스케줄러 ==="
    launchctl list | grep contents-pipeline || echo "등록 안 됨"
    ;;
  run-now)
    case "$2" in
      health) launchctl start com.contents-pipeline.health; echo "✅ 건강블로그 즉시 실행" ;;
      *)      launchctl start com.contents-pipeline.daily;  echo "✅ 지원금블로그 즉시 실행" ;;
    esac
    ;;
  *)
    echo "사용법: $0 {install|uninstall|status|run-now [health]}"
    ;;
esac
