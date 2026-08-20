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
        # Report the exit code, not just "FAIL". A test whose own checks all pass
        # can still exit non-zero — Qt's teardown under the offscreen platform
        # crashes on a machine with no GPU, which is why 41 of these scripts end
        # in os._exit(). Without the code, that case reads as a failing assertion
        # and sends you looking in the wrong place; 139 says "signal 11 at exit"
        # at a glance.
        echo "FAIL  $t (exit $?)"
        sed 's/^/    | /' /tmp/hybmesh_test.$$.log | tail -20
        fail=$((fail + 1))
        failed+=("$t")
    fi
done
# The C++ unit tests (ctest). They live in the build tree, so this self-skips
# when there is none — the same convention the binary-dependent Python tests use,
# which is what keeps `run_all.sh` the ONE command a developer runs while still
# counting the C++ side into the total. Each registered test is invoked through
# ctest rather than by running the executable directly: going around the
# registration would let a test that CMake never registered pass silently, which
# is exactly what test_cpp_linkable_seam.py check 6 exists to prevent.
#
# ctest is invoked by cd-ing into the build tree rather than with `--test-dir`,
# which needs CMake >= 3.20 while this project declares 3.10. With the flag, an
# older ctest rejects the argument, the `-N` listing comes back empty, and the
# loop below contributes ZERO tests while the guard above still passes — a
# silent hole rather than a skip.
BUILD_DIR="$(cd ../../.. && pwd)/build"
if [ -f "$BUILD_DIR/CTestTestfile.cmake" ]; then
    while read -r t; do
        [ -n "$t" ] || continue
        if (cd "$BUILD_DIR" && ctest -R "^${t}\$" --output-on-failure) \
                >/tmp/hybmesh_test.$$.log 2>&1; then
            echo "PASS  $t (C++)"
            pass=$((pass + 1))
        else
            echo "FAIL  $t (C++)"
            sed 's/^/    | /' /tmp/hybmesh_test.$$.log | tail -20
            fail=$((fail + 1))
            failed+=("$t (C++)")
        fi
    done < <(cd "$BUILD_DIR" && ctest -N 2>/dev/null |
             sed -n 's/^ *Test *#[0-9]*: *//p')
else
    echo "SKIP  C++ unit tests (no build tree at $BUILD_DIR — run ./build.sh)"
fi

rm -f /tmp/hybmesh_test.$$.log
echo "-------------------------------------------"
echo "TOTAL: $((pass + fail))   PASS: $pass   FAIL: $fail"
if [ "$fail" -ne 0 ]; then
    echo "FAILED: ${failed[*]}"
    exit 1
fi
