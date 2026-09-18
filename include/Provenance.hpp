#ifndef PROVENANCE_HPP
#define PROVENANCE_HPP

// Output provenance: a machine-readable sidecar written next to every exported
// mesh so a run can be traced back to its tool version, inputs and effective
// config. Hand-formatted JSON via ofstream (no JSON dependency added to src/).

#include "CellShape.hpp"
#include "Config.hpp"
#include "Logger.hpp"
#include <string>
#include <vector>
#include <fstream>
#include <sstream>
#include <ctime>
#include <cstdio>
#include <chrono>

#if __has_include(<filesystem>)
#include <filesystem>
#define HYBMESH_PROV_HAVE_FS 1
#endif

// Version identifiers. The build system MAY define HYBMESH_VERSION / HYBMESH_GIT_SHA;
// fall back so the code still compiles standalone.
#ifndef HYBMESH_VERSION
#define HYBMESH_VERSION "dev"
#endif
#ifndef HYBMESH_GIT_SHA
#define HYBMESH_GIT_SHA "unknown"
#endif

namespace hybmesh {

// Escape a string for embedding in a JSON string literal.
inline std::string jsonEscape(const std::string& s) {
    std::string out;
    out.reserve(s.size() + 8);
    for (char c : s) {
        switch (c) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n";  break;
            case '\r': out += "\\r";  break;
            case '\t': out += "\\t";  break;
            default:
                if (static_cast<unsigned char>(c) < 0x20) {
                    char buf[8];
                    std::snprintf(buf, sizeof(buf), "\\u%04x", c);
                    out += buf;
                } else {
                    out += c;
                }
        }
    }
    return out;
}

// A lightweight fingerprint for one input geometry file: size + mtime. A full
// sha256 is a documented follow-up (not required here).
struct InputFingerprint {
    std::string path;
    long long size = -1;      // bytes, -1 if unknown
    long long mtimeEpoch = -1;// seconds since epoch, -1 if unknown
};

inline InputFingerprint fingerprintOf(const std::string& path) {
    InputFingerprint fp;
    fp.path = path;
#ifdef HYBMESH_PROV_HAVE_FS
    std::error_code ec;
    auto sz = std::filesystem::file_size(path, ec);
    if (!ec) fp.size = static_cast<long long>(sz);
    auto ft = std::filesystem::last_write_time(path, ec);
    if (!ec) {
        // Best-effort conversion of file_time to epoch seconds.
        auto sctp = std::chrono::time_point_cast<std::chrono::system_clock::duration>(
            ft - std::filesystem::file_time_type::clock::now() +
            std::chrono::system_clock::now());
        fp.mtimeEpoch = static_cast<long long>(
            std::chrono::duration_cast<std::chrono::seconds>(sctp.time_since_epoch()).count());
    }
#endif
    return fp;
}

// Provenance banner lines for embedding at the top of a mesh file (VTK header,
// STAR-CD comment). Caller prefixes each with the format's comment marker.
inline std::vector<std::string> provenanceBanner() {
    std::vector<std::string> lines;
    lines.push_back(std::string("HybMesh2D ") + HYBMESH_VERSION + " (git " + HYBMESH_GIT_SHA + ")");
    lines.push_back(std::string("Exported ") + utcTimestamp());
    return lines;
}

// Resolve the Gmsh version string for provenance. gmshVersionStr may be supplied
// by the caller (after gmsh::option::getString) — otherwise use the API macros.
inline std::string gmshVersionFallback() {
#if defined(GMSH_API_VERSION)
    return std::string(GMSH_API_VERSION);
#else
    return std::string("unknown");
#endif
}

// THE MESH-QUALITY HALF OF THE SIDECAR (issue #129, parent #128).
//
// The sidecar is the CONTRACT every downstream reader uses — the GUI panel, the
// pipeline runner, the batch queue — which is what makes the mesher the single
// OWNER of "how good is this mesh" instead of each surface computing its own and
// two of them disagreeing about the same file. It is also what makes the numbers
// outlive the process: a mesh opened three sessions later still carries them.
//
// `metric` NAMES the quantity, because the two generation paths measure two
// different things (`quad_midline_ratio` on multi-block's structured quads since
// #129, `tri_edge_ratio` on the hybrid path's exported triangles since #130) and a
// reader that compares one against the other is comparing nothing. Both are
// emitted today, so a sidecar that names neither is a third case and not a default.
// An EMPTY metric writes no `quality` object at all, which is the honest answer for
// a path that does not measure — as opposed to writing one full of zeros.
//
// A metric that IS named always writes the object, even when nothing could be
// measured: then `cells` is 0 and the three figures are negative, which says "we
// looked and could not measure" rather than leaving a reader to guess between
// that and "this tool does not measure".
//
// THE SPLIT IS A SEPARATE STATE FROM AN UNMEASURED SET (issue #143). `split` says
// whether the producing path separated its near-surface cells from the rest at
// all; `layer` and `bulk` are written only when it did, and a path that does not
// split writes neither key rather than two objects full of negatives. A path that
// DOES split and found one half empty writes that half with `cells` 0 and negative
// figures, which is the ordinary state of a geometry meshed with no boundary layer
// — the same distinction `metric` already draws between "this tool does not
// measure" and "we looked and could not measure".
//
// THE WHOLE-MESH KEYS DO NOT MOVE. `cells`, `median`, `p95` and `max` stay where
// #129 put them, directly on `quality`, so a reader that knows only those keys
// still reads the figures it always read out of a sidecar written after this work.
struct MeshQuality {
    std::string metric;                 // empty -> no quality object is written
    hybmesh::ShapeStats shape;
    bool split = false;                 // false -> no layer/bulk keys are written
    hybmesh::ShapeStats layer;          // the near-surface cells
    hybmesh::ShapeStats bulk;           // the rest
};

// Write "<basename>.provenance.json" next to the export. `basename` is the output
// path stripped of its extension (e.g. Results/mesh_naca). Returns false on I/O
// failure (logged, but never fatal to the run).
inline bool writeProvenance(const std::string& basename,
                            const Config& config,
                            const std::vector<std::string>& inputFiles,
                            const std::string& gmshVersion,
                            size_t nNodes, size_t nElements,
                            const MeshQuality& quality = MeshQuality{}) {
    const std::string path = basename + ".provenance.json";
    std::ofstream ofs(path);
    if (!ofs) {
        LOG_WARN("Could not write provenance sidecar '" << path << "'.");
        return false;
    }
    ofs << "{\n";
    ofs << "  \"tool\": \"HybMesh2D\",\n";
    ofs << "  \"version\": \"" << jsonEscape(HYBMESH_VERSION) << "\",\n";
    ofs << "  \"git_sha\": \"" << jsonEscape(HYBMESH_GIT_SHA) << "\",\n";
    ofs << "  \"timestamp_utc\": \"" << jsonEscape(utcTimestamp()) << "\",\n";
    ofs << "  \"gmsh_version\": \"" << jsonEscape(gmshVersion.empty() ? gmshVersionFallback() : gmshVersion) << "\",\n";
    ofs << "  \"mesh\": { \"nodes\": " << nNodes << ", \"elements\": " << nElements;
    if (!quality.metric.empty()) {
        // Nested UNDER `mesh`, because it describes the mesh this file is beside
        // and not the run that made it. Printed at a fixed precision rather than
        // the stream's default, so a reader comparing it against the
        // machine-readable stdout line is comparing the same digits.
        std::ostringstream qs;
        qs << std::fixed;
        qs.precision(6);
        // ONE SPELLING OF THE FOUR FIELD NAMES, for all three sets: the
        // whole-mesh figures sit FLAT on `quality` where #129 put them and the
        // two halves sit in objects of their own, but the keys inside are written
        // once so the three cannot drift apart under an edit meant for one.
        auto writeFields = [&qs](const hybmesh::ShapeStats& st) {
            qs << "\"cells\": " << st.cells
               << ", \"median\": " << st.median
               << ", \"p95\": " << st.p95
               << ", \"max\": " << st.max;
        };
        qs << ", \"quality\": { \"metric\": \"" << jsonEscape(quality.metric)
           << "\", ";
        writeFields(quality.shape);
        if (quality.split) {
            // NESTED, and beside the whole-mesh figures rather than replacing
            // them: a reader that knows only #129's keys reads the same numbers
            // out of the same places, and one that knows these reads the split
            // without having to tell which half it is holding.
            qs << ", \"layer\": { ";
            writeFields(quality.layer);
            qs << " }, \"bulk\": { ";
            writeFields(quality.bulk);
            qs << " }";
        }
        qs << " }";
        ofs << qs.str();
    }
    ofs << " },\n";
    ofs << "  \"inputs\": [\n";
    for (size_t i = 0; i < inputFiles.size(); ++i) {
        InputFingerprint fp = fingerprintOf(inputFiles[i]);
        ofs << "    { \"path\": \"" << jsonEscape(fp.path) << "\", "
            << "\"size\": " << fp.size << ", "
            << "\"mtime_epoch\": " << fp.mtimeEpoch << " }"
            << (i + 1 < inputFiles.size() ? "," : "") << "\n";
    }
    ofs << "  ],\n";
    ofs << "  \"config\": ";
    // Effective, fully-resolved config as a JSON string block (reuses Config::print
    // via the ostream variant; embedded as one escaped string to avoid duplicating
    // the schema here).
    {
        std::ostringstream cfg;
        config.print(cfg);
        ofs << "\"" << jsonEscape(cfg.str()) << "\"\n";
    }
    ofs << "}\n";
    return true;
}

} // namespace hybmesh

#endif // PROVENANCE_HPP
