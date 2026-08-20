#ifndef HYBMESH_TEST_CHECK_HPP
#define HYBMESH_TEST_CHECK_HPP

#include <cmath>
#include <cstdio>
#include <string>

// A minimal assertion harness, deliberately not a framework. Adding a vendored
// single-header framework costs ~10k lines and buys subcases and prettier
// diffs; at this size that is not worth it, and this matches the shape of the
// Python suite next door (each test is a standalone script that exits non-zero).
//
// Failures are RECORDED AND EXECUTION CONTINUES, because ctest runs one
// executable per test file: seeing all the failing cases from a single CI run
// beats bisecting them one at a time. The cost of continuing is that a failed
// check can leave later checks running on bad state, so report() prints the
// FIRST failure again on its own final line — the cause must not end up buried
// under its consequences.
namespace hybmesh::test {

inline int g_failures = 0;
inline std::string g_first;

inline void record(bool ok, const char* expr, const char* file, int line,
                   const std::string& msg) {
    if (ok) return;
    ++g_failures;
    std::string where = std::string(file) + ":" + std::to_string(line)
                      + "  " + msg + "   [" + expr + "]";
    if (g_first.empty()) g_first = where;
    std::printf("FAIL  %s\n", where.c_str());
}

// Return this from main(): 0 only when every check passed.
inline int report(const char* name) {
    if (g_failures == 0) {
        std::printf("PASS  %s\n", name);
        return 0;
    }
    std::printf("\n%d check(s) failed in %s\nFIRST FAILURE: %s\n",
                g_failures, name, g_first.c_str());
    return 1;
}

}  // namespace hybmesh::test

#define CHECK(cond, msg) \
    ::hybmesh::test::record((cond), #cond, __FILE__, __LINE__, (msg))

#define CHECK_NEAR(a, b, tol, msg)                                       \
    ::hybmesh::test::record(std::fabs((a) - (b)) <= (tol), #a " ~= " #b,  \
                            __FILE__, __LINE__, (msg))

#endif
