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

# 反向規則:results/ 底下「除了 KEEP 以外」的東西都算可重生產物。
# 用保留清單而非刪除清單,新增的輸出目錄(例如日後的 contours/)才不會被漏掉
# 而讓腳本誤報「已乾淨」。
KEEP=(inputs resampled logs pipeline .gitkeep)
# solver/ 底下額外保留的名稱:dll_src/ 是 DLL Builder 的預設存檔位置,
# 各 case 的 dll/ 則存放已編譯/可能被手動編輯過的 phi 原始碼 —— 兩者都不可重生。
SOLVER_KEEP=(dll dll_src)

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

shopt -s nullglob dotglob

# in_list <needle> <haystack...> — bash 3.2 (macOS 內建) 沒有關聯陣列,用線性比對。
in_list() {
    local needle="$1"; shift
    local x
    for x in "$@"; do [ "$x" = "$needle" ] && return 0; done
    return 1
}

# 收集實際要刪的路徑。solver/ 需要逐層展開才能保留 dll/ 與 dll_src/。
TARGETS=()
for entry in "${RESULTS_DIR}"/*; do
    base="$(basename "$entry")"
    in_list "$base" "${KEEP[@]}" && continue
    if [ "$base" != "solver" ] || [ ! -d "$entry" ]; then
        TARGETS+=("$entry")
        continue
    fi
    for case_dir in "$entry"/*; do
        cbase="$(basename "$case_dir")"
        in_list "$cbase" "${SOLVER_KEEP[@]}" && continue
        if [ ! -d "$case_dir" ]; then
            TARGETS+=("$case_dir")
            continue
        fi
        # <case>/ 目錄:保留 dll/,其餘(work/ grid/ …)才刪。
        kept=0; items=()
        for item in "$case_dir"/*; do
            ibase="$(basename "$item")"
            if in_list "$ibase" "${SOLVER_KEEP[@]}"; then kept=1; else items+=("$item"); fi
        done
        if [ "$kept" -eq 0 ]; then
            # 沒有要保留的東西,整個 case 目錄一起刪掉,不留空殼。
            TARGETS+=("$case_dir")
        elif [ "${#items[@]}" -gt 0 ]; then
            TARGETS+=("${items[@]}")
        fi
    done
done

echo "results/ 目錄: $RESULTS_DIR"
echo "----------------------------------------"
for target in ${TARGETS[@]+"${TARGETS[@]}"}; do
    # `|| true` so an unreadable file (du/find non-zero under pipefail) can't
    # abort the whole script via set -e; we only need best-effort sizes here.
    size="$(du -sh "$target" 2>/dev/null | cut -f1 || true)"
    nfiles="$(find "$target" -type f 2>/dev/null | wc -l | tr -d ' ' || true)"
    printf "  %-30s %6s  (%s 檔)\n" "${target#${RESULTS_DIR}/}" "$size" "$nfiles"
done

if [ "${#TARGETS[@]}" -eq 0 ]; then
    echo "沒有可清理的產物,results/ 已乾淨。"
    exit 0
fi

echo "----------------------------------------"
echo "保留: ${KEEP[*]} (solver/ 底下另保留: ${SOLVER_KEEP[*]})"

if [ "$FORCE" -ne 1 ]; then
    echo
    echo "[DRY-RUN] 以上為「會被刪除」的目標,尚未刪除。"
    echo "          確認無誤後,加 --force 實際刪除:"
    echo "          $0 --force"
    exit 0
fi

echo
for target in ${TARGETS[@]+"${TARGETS[@]}"}; do
    [ -e "$target" ] || continue
    rm -rf "$target" && echo "已刪除 ${target#${RESULTS_DIR}/}"
done
echo "----------------------------------------"
echo "完成。results/ 現在大小: $(du -sh "$RESULTS_DIR" 2>/dev/null | cut -f1 || true)"
