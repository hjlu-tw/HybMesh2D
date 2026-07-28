#!/usr/bin/env bash
#
# clean_results.sh — 清理 results/ 底下可重生的產物,保留 CAD 來源與腳本。
#
# results/ 全部 git-ignored,這裡刪的都是跑 mesh / solver / stl3d 能重生的輸出。
# 預設為 dry-run(只列出、不刪),確認無誤後加 --force 才真的刪除。
#
# 用法:
#   ./tools/scripts/clean_results.sh            # dry-run,顯示會刪什麼、能釋放多少
#   ./tools/scripts/clean_results.sh --force    # 實際刪除
#   ./tools/scripts/clean_results.sh -h         # 說明
#
set -euo pipefail

# 專案根目錄 = 本腳本的 ../../
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
RESULTS_DIR="${ROOT_DIR}/results"

# 會被刪除的可重生產物子目錄(相對 results/)
DELETE=(meshes solver junction_png stl3d u1test)
# 保留:inputs(CAD 來源)、resampled、logs、pipeline(腳本)、.gitkeep

FORCE=0
for arg in "$@"; do
    case "$arg" in
        --force|-f) FORCE=1 ;;
        -h|--help)
            sed -n '2,/^set -/{/^set -/d;s/^# \{0,1\}//p;}' "${BASH_SOURCE[0]}"
            exit 0 ;;
        *) echo "未知參數: $arg (用 -h 看說明)" >&2; exit 2 ;;
    esac
done

if [ ! -d "$RESULTS_DIR" ]; then
    echo "找不到 results/ 目錄: $RESULTS_DIR" >&2
    exit 1
fi

echo "results/ 目錄: $RESULTS_DIR"
echo "----------------------------------------"
total_targets=0
for sub in "${DELETE[@]}"; do
    target="${RESULTS_DIR}/${sub}"
    [ -e "$target" ] || continue
    # `|| true` so an unreadable file (du/find non-zero under pipefail) can't
    # abort the whole script via set -e; we only need best-effort sizes here.
    size="$(du -sh "$target" 2>/dev/null | cut -f1 || true)"
    nfiles="$(find "$target" -type f 2>/dev/null | wc -l | tr -d ' ' || true)"
    printf "  %-14s %6s  (%s 檔)\n" "$sub/" "$size" "$nfiles"
    total_targets=$((total_targets + 1))
done

if [ "$total_targets" -eq 0 ]; then
    echo "沒有可清理的產物,results/ 已乾淨。"
    exit 0
fi

echo "----------------------------------------"
echo "保留: inputs/ resampled/ logs/ pipeline/ .gitkeep"

if [ "$FORCE" -ne 1 ]; then
    echo
    echo "[DRY-RUN] 以上為「會被刪除」的目標,尚未刪除。"
    echo "          確認無誤後,加 --force 實際刪除:"
    echo "          $0 --force"
    exit 0
fi

echo
for sub in "${DELETE[@]}"; do
    target="${RESULTS_DIR}/${sub}"
    [ -e "$target" ] || continue
    rm -rf "$target" && echo "已刪除 ${sub}/"
done
echo "----------------------------------------"
echo "完成。results/ 現在大小: $(du -sh "$RESULTS_DIR" 2>/dev/null | cut -f1 || true)"
