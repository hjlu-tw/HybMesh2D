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
    // Multi-block path (MESH_MODE 1). Two codes rather than one, because the
    // caller's response differs: fix the declaration, versus look at the mesh.
    EXIT_ERR_TOPOLOGY     = 8, // topology declaration invalid -> nothing exported
    // Declared before it has an emitter, deliberately and on the ticket's own
    // instruction ("Two new exit codes are declared with stable machine-readable
    // tokens"): the point of #49 is that a caller can learn to branch on both codes
    // NOW and keep working when the path lands. That is in tension with this repo's
    // "a branch nothing can reach reads as a working feature" rule, so it is written
    // down rather than left to be rediscovered — the difference is that this is a
    // published CONSTANT, not a branch claiming to do something.
    EXIT_ERR_INVERTED     = 9, // mesh generated but holds inverted cells -> EXPORTED anyway
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
        case EXIT_ERR_TOPOLOGY:      return "TOPOLOGY";
        case EXIT_ERR_INVERTED:      return "INVERTED";
        default:                     return "UNKNOWN";
    }
}

#endif // EXITCODES_HPP
