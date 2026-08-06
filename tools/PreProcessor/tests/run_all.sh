#!/usr/bin/env bash
# Run every headless GUI/model regression test and report a summary.
#
# Each test_*.py / smoke_*.py is a standalone script that self-selects the
# offscreen Qt platform and exits non-zero on failure (tests needing the
# compiled C++ binaries self-skip when those are absent, so this is safe
# without a build).
#
# Exit code: 0 if all tests pass, 1 if any fail.
set -u
cd "$(dirname "$0")"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"

# nullglob: an unmatched pattern must expand to nothing rather than to its own
# literal text, which python3 would then "fail" to run and report as a bogus FAIL.
shopt -s nullglob
scripts=(test_*.py smoke_*.py)
if [ "${#scripts[@]}" -eq 0 ]; then
    echo "找不到任何 test_*.py / smoke_*.py" >&2
    exit 1
fi

pass=0; fail=0; failed=()
for t in "${scripts[@]}"; do
    if python3 "$t" >/tmp/hybmesh_test.$$.log 2>&1; then
        echo "PASS  $t"
        pass=$((pass + 1))
    else
        echo "FAIL  $t"
        sed 's/^/    | /' /tmp/hybmesh_test.$$.log | tail -20
        fail=$((fail + 1))
        failed+=("$t")
    fi
done
rm -f /tmp/hybmesh_test.$$.log
echo "-------------------------------------------"
echo "TOTAL: $((pass + fail))   PASS: $pass   FAIL: $fail"
if [ "$fail" -ne 0 ]; then
    echo "FAILED: ${failed[*]}"
    exit 1
fi
