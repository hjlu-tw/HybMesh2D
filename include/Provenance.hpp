#ifndef PROVENANCE_HPP
#define PROVENANCE_HPP

// Output provenance: a machine-readable sidecar written next to every exported
// mesh so a run can be traced back to its tool version, inputs and effective
// config. Hand-formatted JSON via ofstream (no JSON dependency added to src/).

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

// Write "<basename>.provenance.json" next to the export. `basename` is the output
// path stripped of its extension (e.g. Results/mesh_naca). Returns false on I/O
// failure (logged, but never fatal to the run).
inline bool writeProvenance(const std::string& basename,
                            const Config& config,
                            const std::vector<std::string>& inputFiles,
                            const std::string& gmshVersion,
                            size_t nNodes, size_t nElements) {
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
    ofs << "  \"mesh\": { \"nodes\": " << nNodes << ", \"elements\": " << nElements << " },\n";
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
