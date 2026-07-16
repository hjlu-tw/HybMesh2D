#ifndef LOGGER_HPP
#define LOGGER_HPP

// Minimal leveled logger with a UTC timestamp prefix.
//   LOG_INFO  -> stdout
//   LOG_WARN  -> stderr
//   LOG_ERROR -> stderr
// All levels are also teed to a per-run log file
//   results/logs/run-<timestamp>-<pid>.log
// created lazily on the first log call. A file-open failure is ignored (logging
// still goes to the console) so logging never becomes a hard dependency.
//
// Header-only and self-contained (no build-system wiring): every translation
// unit that includes it shares the same file via a function-local static.

#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <ctime>
#include <mutex>
#include <cstdio>

#if defined(_WIN32)
#include <process.h>
#define HYBMESH_GETPID _getpid
#else
#include <unistd.h>
#define HYBMESH_GETPID getpid
#endif

// filesystem is used only to create the log directory; guarded so a toolchain
// without <filesystem> still compiles (it just won't create the dir).
#if __has_include(<filesystem>)
#include <filesystem>
#define HYBMESH_HAVE_FS 1
#endif

namespace hybmesh {

inline std::string utcTimestamp() {
    std::time_t t = std::time(nullptr);
    std::tm tmv{};
#if defined(_WIN32)
    gmtime_s(&tmv, &t);
#else
    gmtime_r(&t, &tmv);
#endif
    char buf[32];
    std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &tmv);
    return std::string(buf);
}

class Logger {
public:
    static Logger& instance() {
        static Logger inst;
        return inst;
    }

    void log(const char* level, std::ostream& console, const std::string& msg) {
        std::lock_guard<std::mutex> lk(m_mutex);
        std::string line = "[" + utcTimestamp() + "] [" + level + "] " + msg;
        console << line << std::endl;
        if (!m_fileTried) openFile();
        if (m_file.is_open()) m_file << line << std::endl;
    }

private:
    Logger() = default;

    void openFile() {
        m_fileTried = true;
        std::string dir = "results/logs";
#ifdef HYBMESH_HAVE_FS
        std::error_code ec;
        std::filesystem::create_directories(dir, ec);
        if (ec) return; // cannot create dir -> console-only, no hard failure
#endif
        std::ostringstream path;
        path << dir << "/run-" << utcTimestamp() << "-"
             << (long)HYBMESH_GETPID() << ".log";
        m_file.open(path.str(), std::ios::app);
        // If open fails, is_open() stays false and we silently stay console-only.
    }

    std::mutex m_mutex;
    std::ofstream m_file;
    bool m_fileTried = false;
};

} // namespace hybmesh

// Convenience macros. Accept a streaming expression, e.g. LOG_ERROR("bad " << x).
#define LOG_INFO(expr)  do { std::ostringstream _oss; _oss << expr; ::hybmesh::Logger::instance().log("INFO",  std::cout, _oss.str()); } while (0)
#define LOG_WARN(expr)  do { std::ostringstream _oss; _oss << expr; ::hybmesh::Logger::instance().log("WARN",  std::cerr, _oss.str()); } while (0)
#define LOG_ERROR(expr) do { std::ostringstream _oss; _oss << expr; ::hybmesh::Logger::instance().log("ERROR", std::cerr, _oss.str()); } while (0)

#endif // LOGGER_HPP
