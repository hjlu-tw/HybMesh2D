#ifndef EXITCODES_HPP
#define EXITCODES_HPP

// Distinct process exit codes so a caller (the GUI, a CI script, run_pipeline.py)
// can tell WHY a run failed without parsing prose. Each failure class also emits
// a machine-readable "HYBMESH_ERROR <code> <token> ..." line (see reportError()).
enum ExitCode {
    EXIT_OK               = 0,
    EXIT_ERR_CONFIG       = 2, // config file missing/invalid or failed validation
    EXIT_ERR_GEOMETRY_LOAD= 3, // a requested geometry could not be loaded
    EXIT_ERR_INTERSECTION = 4, // geometries intersect / cross the domain boundary
    EXIT_ERR_BL           = 5, // boundary-layer growth failed
    EXIT_ERR_GMSH         = 6, // Gmsh far-field triangulation failed / empty mesh
    EXIT_ERR_EXPORT       = 7, // mesh export failed
};

// Short stable token per exit code for the machine-readable error line.
inline const char* exitCodeToken(int code) {
    switch (code) {
        case EXIT_ERR_CONFIG:        return "CONFIG";
        case EXIT_ERR_GEOMETRY_LOAD: return "GEOMETRY_LOAD";
        case EXIT_ERR_INTERSECTION:  return "INTERSECTION";
        case EXIT_ERR_BL:            return "BL";
        case EXIT_ERR_GMSH:          return "GMSH";
        case EXIT_ERR_EXPORT:        return "EXPORT";
        default:                     return "UNKNOWN";
    }
}

#endif // EXITCODES_HPP
