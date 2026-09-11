// exportVTK's ALL-OR-NOTHING block-id rule, driven from the state no production
// path can reach (#113, under #108).
//
// `src/Mesh.cpp::exportVTK` writes the `CELL_DATA`/`SCALARS block` section only
// when EVERY element carries a block id, and warns when SOME do. A VTK scalar
// array has one value per cell and no way to spell "this cell has none", so a
// partially tagged mesh could only be written with a sentinel — the thing
// `Element::blockId` is an `std::optional` in order to avoid.
//
// tools/PreProcessor/tests/test_multiblock_block_field.py covers that rule from
// the outside on the SHIPPED configs, and named this as its one uncovered state:
// the `MESH_MODE 1` adapter's single loop tags every cell it adds, so no run can
// produce a partially tagged mesh and the warning branch was unexercised. That
// makes it UNREACHABLE FROM PRODUCTION, not untestable — `Mesh` is a library
// target this tree links (see tests/cpp/CMakeLists.txt), so the state can simply
// be built here. That distinction is the whole reason this file exists.
//
// What is asserted is the OBSERVABLE OUTCOME, never the branch: what the file on
// disk looks like. And the fully tagged mesh is exported as a NEGATIVE CONTROL,
// so "no section" cannot be what this test would report either way — a writer
// that never wrote the section at all would fail here rather than pass twice.
//
// VERIFIED BY INJECTION into src/Mesh.cpp, 2026-09-11, each one restored and
// REBUILT before the next, and the EXIT CODE read first (a test that crashes
// prints no further FAIL lines and would look like a weaker bite than it is):
//
//   * silence the warning, `if (false)`.                 -> exit 1, 3 FAIL, all
//     in group 2. Groups 1 and 3-5 stay green, which is correct: the FILE is
//     unchanged, and this injection is what shows group 2 is not re-asserting
//     group 1.
//   * drop the guard and write a sentinel, `if (true)` with
//     `el.blockId ? *el.blockId : 0`.                    -> exit 1, 6 FAIL, in
//     groups 1 (including the byte-equality check), 4 and 5. This is the whole
//     defect the rule exists to prevent, and it is caught in three states.
//   * never write the section at all.                    -> exit 1, 4 FAIL, ALL
//     of them group 3. The negative control doing its one job: without it every
//     absence check above would pass on a writer that had lost the field.
//   * drop the `!elements.empty()` clause.               -> exit 1, 1 FAIL, the
//     empty-mesh check alone. That clause is not redundant with the count test:
//     at zero cells `tagged == elements.size()` holds vacuously.
//   * write a constant value for every cell.             -> exit 1, 1 FAIL.
//   * rename the array, `SCALARS blockId int 1`.         -> exit 1, 1 FAIL, the
//     header pin alone -- the content is unchanged, and the array name is what
//     a reader selects in ParaView, so it is interface.
//   * NEGATIVE CONTROL, unmutated tree.                  -> exit 0.
//
// Two of those were found by the injections rather than confirmed by them, and
// both were defects in THIS FILE:
//   * The third injection scored exit 134 on its first run, not 1: the
//     value-order check handed `find`'s npos to `substr` and the run ended in an
//     uncaught exception before groups 4 and 5 reported. The check tests the
//     position first now -- see the comment there.
//   * Group 1's equality check was a RAW byte comparison and passed for several
//     runs before failing once the machine was loaded: line 2 of every export
//     carries a UTC timestamp at second resolution, so two exports from one
//     process differ there the moment they straddle a second. It compares
//     everything but that line now -- see `withoutProvenance`. A flake that only
//     appears under load is worse than no check, and it was a documented
//     property of this exporter before this file walked into it.
//
// BLIND SPOTS:
//   * Nothing here asserts the state stays UNREACHABLE from production. A
//     MESH_MODE 1 change adding one untagged cell would make the whole field
//     vanish, caught by the warning at run time and by no gate; that hole is
//     named in .claude/rules/mesher-multiblock.md.
//   * The warning is matched on its counts and on the phrase naming the omitted
//     field, not on its whole text, so a rewording that kept both would pass.
//     The counts are the part a reader acts on.
//   * The mesh here is built by hand, so nothing joins this file's four states
//     to what the MESH_MODE 1 adapter actually produces. That join is
//     tools/PreProcessor/tests/test_multiblock_block_field.py's, through the
//     real binary on the shipped configs.
#include "check.hpp"

#include "Mesh.hpp"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace {

// Four quads in a row, sharing nodes: a mesh small enough to read whole and big
// enough for "some but not all" to be an interesting fraction.
constexpr int kCells = 4;

// `tagCount` cells get a block id (0, 1, 2, ...); the rest get none.
Mesh stripMesh(int tagCount) {
    Mesh m;
    for (int i = 0; i <= kCells; ++i) {
        m.addNode({static_cast<double>(i), 0.0}, NodeType::Boundary);
        m.addNode({static_cast<double>(i), 1.0}, NodeType::Boundary);
    }
    for (int c = 0; c < kCells; ++c) {
        std::vector<int> ids{2 * c, 2 * c + 2, 2 * c + 3, 2 * c + 1};
        if (c < tagCount) m.addElement(ids, c);
        else              m.addElement(ids);
    }
    return m;
}

std::string readAll(const std::filesystem::path& p) {
    std::ifstream ifs(p);
    std::ostringstream oss;
    oss << ifs.rdbuf();
    return oss.str();
}

// The whole log seam for a WARN is `console << line`, with `console` bound to
// std::cerr (include/Logger.hpp), so swapping that stream's buffer captures it.
// Acceptance criterion 3 of #113 asks for the warning to be asserted "if the log
// seam allows it to be captured": it does, and this is how.
struct CapturedStderr {
    std::ostringstream buf;
    std::streambuf* prev = std::cerr.rdbuf(buf.rdbuf());
    ~CapturedStderr() { std::cerr.rdbuf(prev); }
    std::string str() { std::cerr.flush(); return buf.str(); }
};

// The four .vtk files go somewhere disposable — but the reason this is a cwd
// change rather than four absolute paths is the LOGGER: it tees every line to
// results/logs/run-<stamp>-<pid>.log RELATIVE TO THE CWD, so a test that emits
// the warning from the build tree would leave a run log behind on every ctest.
struct InTempDir {
    std::filesystem::path dir;
    std::filesystem::path prev = std::filesystem::current_path();
    explicit InTempDir(const char* name)
        : dir(std::filesystem::temp_directory_path() / name) {
        std::filesystem::remove_all(dir);
        std::filesystem::create_directories(dir);
        std::filesystem::current_path(dir);
    }
    ~InTempDir() {
        std::filesystem::current_path(prev);
        std::error_code ec;
        std::filesystem::remove_all(dir, ec);
    }
};

bool has(const std::string& hay, const std::string& needle) {
    return hay.find(needle) != std::string::npos;
}

// Line 2 of every export is the provenance banner: version, git sha and an
// `Exported <UTC timestamp>` at SECOND resolution. Two exports from the same
// process differ there the moment they straddle a second boundary, so a raw
// byte comparison of two files is a flake, not a check. MEASURED, not reasoned
// about: the comparison below passed for several runs and then failed once the
// machine was loaded enough to push the two exports into different seconds.
// docs/design_notes/mesher.md says the same thing under "WHY 'BYTE-IDENTICAL'
// IS NOT THE FORM THE HYBRID CLAIM TAKES".
std::string withoutProvenance(const std::string& vtk) {
    const size_t first = vtk.find('\n');
    if (first == std::string::npos) return vtk;
    const size_t second = vtk.find('\n', first + 1);
    if (second == std::string::npos) return vtk;
    return vtk.substr(0, first + 1) + vtk.substr(second + 1);
}

}  // namespace

int main() {
    using hybmesh::test::report;

    InTempDir tmp("hybmesh_test_vtk_block_field");

    // Each mesh is exported with stderr captured, so the same run answers both
    // "what is in the file" and "what did the writer say".
    std::string partialErr, fullErr, noneErr, emptyErr;
    {
        CapturedStderr cap;
        stripMesh(kCells - 1).exportVTK("partial.vtk");
        partialErr = cap.str();
    }
    {
        CapturedStderr cap;
        stripMesh(kCells).exportVTK("full.vtk");
        fullErr = cap.str();
    }
    {
        CapturedStderr cap;
        stripMesh(0).exportVTK("none.vtk");
        noneErr = cap.str();
    }
    {
        CapturedStderr cap;
        Mesh().exportVTK("empty.vtk");
        emptyErr = cap.str();
    }

    const std::string partial = readAll(tmp.dir / "partial.vtk");
    const std::string full    = readAll(tmp.dir / "full.vtk");
    const std::string none    = readAll(tmp.dir / "none.vtk");
    const std::string empty   = readAll(tmp.dir / "empty.vtk");

    // --- 1. a partially tagged mesh gets NO block-id section -------------------
    // Not "a section of -1", not "a section of 0": nothing. Both spellings are
    // checked because a sentinel section would still be a `CELL_DATA` block, and
    // a `SCALARS` line under some other header would still be read as a field.
    CHECK(!partial.empty(), "the partially tagged mesh exported a file at all");
    CHECK(!has(partial, "CELL_DATA"),
          "a partially tagged mesh gets no CELL_DATA section");
    CHECK(!has(partial, "SCALARS"),
          "...and no SCALARS array anywhere in the file");
    CHECK(!has(partial, "LOOKUP_TABLE"),
          "...nor the lookup table that would accompany one");

    // The refusal costs the file NOTHING ELSE. Equality against the same mesh
    // with no tags at all is the strongest available statement of "the section
    // simply does not appear": any sentinel, any truncation, any reordering of
    // the cells would break it. Everything but the provenance line is compared,
    // for the reason stated at `withoutProvenance` — that line carries a
    // timestamp and is the one part of an export that is allowed to differ.
    CHECK(withoutProvenance(partial) == withoutProvenance(none),
          "the partially tagged file is identical to the untagged one, "
          "provenance line aside");
    CHECK(!withoutProvenance(partial).empty() &&
              withoutProvenance(partial) != partial,
          "...and that comparison really did drop a line, rather than "
          "comparing two empty strings");
    CHECK(has(partial, "CELLS 4 ") && has(partial, "CELL_TYPES 4"),
          "...and still carries its four cells, so 'no section' is not 'no mesh'");

    // --- 2. the refusal is SAID, not silent -----------------------------------
    // The branch guards a debug aid that would otherwise vanish without saying
    // so, which is indistinguishable from one that was never built.
    CHECK(has(partialErr, "WARN"),
          "the partially tagged export emits a warning");
    CHECK(has(partialErr, "3 of 4"),
          "...naming how many cells carry a block id, and out of how many");
    CHECK(has(partialErr, "block-id cell field"),
          "...and naming the field that was omitted");

    // --- 3. NEGATIVE CONTROL: fully tagged still gets the section -------------
    // Without this, a writer that had simply stopped writing the field would
    // pass group 1 and the test would prove nothing.
    CHECK(has(full, "CELL_DATA 4"),
          "a fully tagged mesh gets a CELL_DATA section, one entry per cell");
    CHECK(has(full, "SCALARS block int 1"),
          "...declared with the array name, type and component count pinned");
    CHECK(has(full, "LOOKUP_TABLE default"), "...and its lookup table");
    {
        // The values, in cell order: 0 1 2 3, one per line, after the table line.
        // `pos` is tested rather than fed straight to substr, because the check
        // above is allowed to have already failed: an injection that removes the
        // section entirely must be able to report THAT and keep going, and
        // substr(npos) would end the run in an uncaught exception instead — a
        // crash prints no further FAIL lines and this repo has scored exactly
        // that as a bite that never happened.
        const size_t pos = full.find("LOOKUP_TABLE default");
        std::vector<std::string> vals;
        if (pos != std::string::npos) {
            std::istringstream iss(full.substr(pos));
            std::string line;
            std::getline(iss, line);  // the LOOKUP_TABLE line itself
            while (std::getline(iss, line)) if (!line.empty()) vals.push_back(line);
        }
        CHECK(vals == std::vector<std::string>({"0", "1", "2", "3"}),
              "the values are the block indices, in cell order");
    }
    CHECK(fullErr.empty(),
          "a fully tagged export warns about nothing");

    // --- 4. the third state: no cell tagged -----------------------------------
    // The rule is all-or-NOTHING, and `none` is a legitimate answer — it is what
    // every hybrid-path run produces. It must not warn: there is nothing partial
    // about it.
    CHECK(!has(none, "CELL_DATA") && !has(none, "SCALARS"),
          "an untagged mesh gets no block-id section");
    CHECK(noneErr.empty(),
          "...and no warning, because nothing was omitted");

    // --- 5. an empty mesh is not vacuously 'fully tagged' ---------------------
    // tagged == elements.size() holds trivially at zero cells, so without the
    // emptiness guard the file would grow a `CELL_DATA 0` header with no values.
    CHECK(!has(empty, "CELL_DATA") && !has(empty, "SCALARS"),
          "an empty mesh gets no block-id section either");
    CHECK(emptyErr.empty(), "...and no warning");

    return report("test_mesh_vtk_block_field");
}
