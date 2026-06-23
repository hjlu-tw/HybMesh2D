#include "Mesh.hpp"
#include "Config.hpp"
#include "BoundaryLayer.hpp"
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <map>
#include <filesystem>

namespace fs = std::filesystem;

std::vector<Point2D> loadGeometry(const std::string& filename) {
    std::vector<Point2D> points;
    std::ifstream ifs(filename);
    if (!ifs) return points;
    double x, y;
    while (ifs >> x >> y) points.push_back({x, y});

    // 如果起點與終點重合，移除最後一個點以避免產生重疊的邊界節點，這會導致法向量計算錯誤
    if (points.size() > 1) {
        double dx = points.front().x - points.back().x;
        double dy = points.front().y - points.back().y;
        if (dx * dx + dy * dy < 1e-12) {
            points.pop_back();
        }
    }
    return points;
}

// Phase 1: optional metadata sidecar produced by the preprocessor next to the
// .dat (see saveMetadata in tools/PreProcessor/src/main.cpp). Parsed with the
// stream extractor only — no JSON dependency. A missing or malformed sidecar
// returns valid==false and the caller transparently falls back to the legacy
// behaviour (BC from config, no corner info).
struct SurfaceMeta {
    bool valid = false;
    std::vector<int> segId;             // parallel to the .dat points
    std::vector<char> isCorner;         // parallel to the .dat points
    std::map<int, std::string> segBc;   // seg_id -> boundary condition tag
    std::map<int, std::string> segKind; // seg_id -> curve kind (v2+)
    std::vector<size_t> pieceBreaks;
};

SurfaceMeta loadSurfaceMeta(const std::string& datFile) {
    SurfaceMeta m;
    std::ifstream ifs(datFile + ".meta");
    if (!ifs) return m;
    std::string tok;
    int version = 0;
    if (!(ifs >> tok >> version) || tok != "HYBMESH_META") return m;
    size_t count = 0, nPieces = 0, nSeg = 0, nPts = 0;
    if (!(ifs >> tok >> count) || tok != "COUNT") return m;
    if (!(ifs >> tok >> nPieces) || tok != "NPIECES") return m;
    for (size_t i = 0; i < nPieces; ++i) { size_t b; if (!(ifs >> b)) return m; m.pieceBreaks.push_back(b); }
    if (!(ifs >> tok >> nSeg) || tok != "NSEGMENTS") return m;
    for (size_t i = 0; i < nSeg; ++i) {
        int sid; std::string bc;
        if (!(ifs >> sid >> bc)) return m;
        m.segBc[sid] = (bc == "-") ? std::string() : bc;
        if (version >= 2) {              // v2 carries the curve kind per segment
            std::string kind;
            if (!(ifs >> kind)) return m;
            m.segKind[sid] = kind;
        }
    }
    if (!(ifs >> tok >> nPts) || tok != "POINTS") return m;
    m.segId.reserve(nPts);
    m.isCorner.reserve(nPts);
    for (size_t i = 0; i < nPts; ++i) {
        int sid = -1, corner = 0;
        if (!(ifs >> sid >> corner)) return m;
        m.segId.push_back(sid);
        m.isCorner.push_back((char)(corner != 0));
    }
    m.valid = true;
    return m;
}

bool checkDomainIntersection(const std::vector<Point2D>& geom, const Config& config) {
    std::vector<Point2D> domain = {
        {config.xMin, config.yMin}, {config.xMax, config.yMin},
        {config.xMax, config.yMax}, {config.xMin, config.yMax}
    };
    
    int nGeom = static_cast<int>(geom.size());
    for (int i = 0; i < nGeom; ++i) {
        Point2D g1 = geom[i];
        Point2D g2 = geom[(i + 1) % nGeom];

        for (int j = 0; j < 4; ++j) {
            Point2D d1 = domain[j];
            Point2D d2 = domain[(j + 1) % 4];

            if (segmentsIntersect(g1, g2, d1, d2)) {
                return true;
            }
        }
    }
    return false;
}

bool isPointInPolygon(Point2D p, const std::vector<Point2D>& poly) {
    int n = static_cast<int>(poly.size());
    bool inside = false;
    for (int i = 0, j = n - 1; i < n; j = i++) {
        if (((poly[i].y > p.y) != (poly[j].y > p.y)) &&
            (p.x < (poly[j].x - poly[i].x) * (p.y - poly[i].y) / (poly[j].y - poly[i].y) + poly[i].x)) {
            inside = !inside;
        }
    }
    return inside;
}

bool checkGeometriesIntersection(const std::vector<Point2D>& geom1, const std::vector<Point2D>& geom2) {
    int n1 = static_cast<int>(geom1.size());
    int n2 = static_cast<int>(geom2.size());
    
    // 1. 檢查線段是否交叉或重合
    for (int i = 0; i < n1; ++i) {
        Point2D g1_a = geom1[i];
        Point2D g1_b = geom1[(i + 1) % n1];
        for (int j = 0; j < n2; ++j) {
            Point2D g2_a = geom2[j];
            Point2D g2_b = geom2[(j + 1) % n2];
            
            // 正常的交叉檢查
            if (segmentsIntersect(g1_a, g1_b, g2_a, g2_b)) return true;

            // 檢查頂點是否落在另一條線段上 (處理重合或觸碰)
            auto isPointOnSegment = [](Point2D p, Point2D s1, Point2D s2) {
                double cross = (p.y - s1.y) * (s2.x - s1.x) - (p.x - s1.x) * (s2.y - s1.y);
                if (std::abs(cross) > 1e-10) return false;
                double dot = (p.x - s1.x) * (s2.x - s1.x) + (p.y - s1.y) * (s2.y - s1.y);
                if (dot < 0) return false;
                double squaredLength = (s2.x - s1.x) * (s2.x - s1.x) + (s2.y - s1.y) * (s2.y - s1.y);
                if (dot > squaredLength) return false;
                return true;
            };

            if (isPointOnSegment(g1_a, g2_a, g2_b)) return true;
            if (isPointOnSegment(g2_a, g1_a, g1_b)) return true;
        }
    }

    // 2. 檢查一個幾何是否完全在另一個內部
    if (isPointInPolygon(geom1[0], geom2)) return true;
    if (isPointInPolygon(geom2[0], geom1)) return true;

    return false;
}

int main(int argc, char* argv[]) {
    Config config;
    std::string configFile = "config/Background_para.dat";
    std::vector<std::string> cmdGeomFiles;
    bool geomProvided = false;
    bool confExplicit = false;
    
    // 第一階段：掃描以找出設定檔路徑與 -geom 參數
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-conf" && i + 1 < argc) {
            configFile = argv[++i];
            confExplicit = true;
        } else if (arg == "-geom") {
            geomProvided = true;
            while (i + 1 < argc && argv[i+1][0] != '-') {
                cmdGeomFiles.push_back(argv[++i]);
            }
        } else if (arg[0] != '-' && !confExplicit) {
            // Bare positional config path. Guard with confExplicit so the VALUE
            // of a later value-flag this loop doesn't recognise (e.g. the "1" in
            // "-out_cgns 1") is not mistaken for the config filename.
            configFile = arg;
            confExplicit = true;
        }
    }

    if (!config.loadFromFile(configFile)) return 1;

    // 如果命令列提供了 -geom，則覆蓋設定檔中的幾何物件
    if (geomProvided) {
        config.geomFiles = cmdGeomFiles;
    }

    // 第二階段：處理其他命令列參數，這些參數優先於設定檔
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-bc_xmin" && i + 1 < argc) config.bcXMin = argv[++i];
        else if (arg == "-bc_xmax" && i + 1 < argc) config.bcXMax = argv[++i];
        else if (arg == "-bc_ymin" && i + 1 < argc) config.bcYMin = argv[++i];
        else if (arg == "-bc_ymax" && i + 1 < argc) config.bcYMax = argv[++i];
        else if (arg == "-bc_geom" && i + 1 < argc) config.bcGeom = argv[++i];
        else if (arg == "-out_vtk" && i + 1 < argc) config.exportVTK = (std::stoi(argv[++i]) != 0);
        else if (arg == "-out_starcd" && i + 1 < argc) config.exportStarCD = (std::stoi(argv[++i]) != 0);
        else if (arg == "-out_cgns" && i + 1 < argc) config.exportCGNS = (std::stoi(argv[++i]) != 0);
        else if (arg == "-out_name" && i + 1 < argc) config.outputFilename = argv[++i];
        // -geom 與 -conf 已經處理過，但在這裡跳過它們的參數以避免干擾
        else if (arg == "-geom") {
            while (i + 1 < argc && argv[i+1][0] != '-') ++i;
        }
        else if (arg == "-conf") {
            if (i + 1 < argc) ++i;
        }
    }

    config.print();
    Mesh mesh;

    std::string outputFilename = "Results/mesh_cartesian.vtk";
    if (!config.outputFilename.empty()) {
        outputFilename = config.outputFilename;
    } else if (!config.geomFiles.empty()) {
        if (config.geomFiles.size() == 1) {
            fs::path geomPath(config.geomFiles[0]);
            outputFilename = "Results/mesh_" + geomPath.stem().string() + ".vtk";
        } else {
            outputFilename = "Results/mesh_multiple.vtk";
        }
    }

    // Ensure the output directory exists so VTK/STAR-CD exports do not silently
    // vanish on a fresh clone or case-sensitive filesystem.
    {
        fs::path outParent = fs::path(outputFilename).parent_path();
        if (!outParent.empty()) {
            std::error_code ec;
            fs::create_directories(outParent, ec);
            if (ec) std::cerr << "Warning: cannot create output directory '"
                              << outParent.string() << "': " << ec.message() << std::endl;
        }
    }

    bool hasIntersection = false;
    bool blSuccess = true;
    if (config.geomFiles.empty()) {
        mesh.generateCartesianMesh(config.xMin, config.xMax, config.yMin, config.yMax, config.farFieldSize);
    } else {
        // 加入計算域邊界 (Domain Box) 到 edges
        std::vector<int> domainNodeIds;
        mesh.addNode({config.xMin, config.yMin}, NodeType::Boundary); domainNodeIds.push_back(mesh.nodes.back().id);
        mesh.addNode({config.xMax, config.yMin}, NodeType::Boundary); domainNodeIds.push_back(mesh.nodes.back().id);
        mesh.addNode({config.xMax, config.yMax}, NodeType::Boundary); domainNodeIds.push_back(mesh.nodes.back().id);
        mesh.addNode({config.xMin, config.yMax}, NodeType::Boundary); domainNodeIds.push_back(mesh.nodes.back().id);
        
        for (int i = 0; i < 4; ++i) {
            mesh.addEdge(domainNodeIds[i], domainNodeIds[(i + 1) % 4]);
            mesh.addElement({domainNodeIds[i], domainNodeIds[(i + 1) % 4]}); // 視覺化用
        }

        BoundaryLayerGenerator blGen(mesh, config);
        double lastH = config.blInitialThickness;

        struct GeomData {
            std::string filename;
            std::vector<Point2D> points;
            SurfaceMeta meta;
        };
        std::vector<GeomData> allGeometries;

        for (const auto& gFile : config.geomFiles) {
            std::vector<Point2D> geomPoints = loadGeometry(gFile);
            if (geomPoints.empty()) {
                std::cerr << "Error: Failed to load geometry from " << gFile << std::endl;
                continue;
            }
            if (checkDomainIntersection(geomPoints, config)) {
                std::cerr << "Error: Geometry " << gFile << " intersects with domain boundary. Skipping.\n";
                continue;
            }

            // Reconcile the sidecar with the points actually loaded. loadGeometry
            // drops a trailing duplicate of the first point on closed loops, so
            // the sidecar legitimately has exactly one extra entry; anything else
            // is a stale/edited mismatch and we ignore the sidecar entirely.
            SurfaceMeta meta = loadSurfaceMeta(gFile);
            if (meta.valid) {
                if (meta.segId.size() == geomPoints.size() + 1) {
                    meta.segId.pop_back();
                    meta.isCorner.pop_back();
                } else if (meta.segId.size() != geomPoints.size()) {
                    std::cerr << "Warning: metadata sidecar for " << gFile
                              << " has " << meta.segId.size() << " points but geometry has "
                              << geomPoints.size() << "; ignoring sidecar.\n";
                    meta.valid = false;
                }
            }
            allGeometries.push_back({gFile, geomPoints, meta});
        }

        if (config.enableCollisionDetection) {
            for (size_t i = 0; i < allGeometries.size(); ++i) {
                for (size_t j = i + 1; j < allGeometries.size(); ++j) {
                    if (checkGeometriesIntersection(allGeometries[i].points, allGeometries[j].points)) {
                        std::cerr << "Error: Geometry " << allGeometries[i].filename 
                                  << " and Geometry " << allGeometries[j].filename 
                                  << " intersect. Process stopped.\n";
                        hasIntersection = true;
                    }
                }
            }
        }
        if (hasIntersection) return 1;

        if (config.blAutoTransitionLayers == 1) {
            double totalLen = 0.0; int totalSegments = 0;
            for (const auto& geomData : allGeometries) {
                int np = (int)geomData.points.size();
                for (int i = 0; i < np; ++i) {
                    totalLen += (geomData.points[(i + 1) % np] - geomData.points[i]).length();
                    totalSegments++;
                }
            }
            if (totalSegments > 0) config.globalAvgSegmentLength = totalLen / (double)totalSegments;
        }

        std::vector<std::vector<int>> allBoundaryIds;
        int currentGeomId = 0;
        int taggedCorners = 0;
        for (const auto& geomData : allGeometries) {
            std::vector<int> boundaryIds;
            const SurfaceMeta& meta = geomData.meta;
            for (size_t pi = 0; pi < geomData.points.size(); ++pi) {
                mesh.addNode(geomData.points[pi], NodeType::Boundary);
                Node& nd = mesh.nodes.back();
                nd.geomId = currentGeomId;
                if (meta.valid) {
                    nd.segId = meta.segId[pi];
                    nd.isCorner = meta.isCorner[pi] != 0;
                    if (nd.isCorner) ++taggedCorners;
                    auto it = meta.segBc.find(nd.segId);
                    if (it != meta.segBc.end() && !it->second.empty()) nd.bcTag = it->second;
                    auto kit = meta.segKind.find(nd.segId);
                    if (kit != meta.segKind.end()) nd.curveKind = curveKindFromString(kit->second);
                }
                boundaryIds.push_back(nd.id);
            }
            allBoundaryIds.push_back(boundaryIds);
            currentGeomId++;
        }
        if (taggedCorners > 0)
            std::cout << "  - Surface metadata     : " << taggedCorners << " corner node(s) tagged\n";

        // Phase 2: report the analytic-curve coverage and sanity-check a fit.
        // This is the bridge to Phase 3, where BL growth will query these curves
        // for true tangents/curvature instead of one-sided finite differences.
        {
            int nLine = 0, nCircle = 0, nSmooth = 0, nPoly = 0;
            for (const auto& nd : mesh.nodes) {
                if (nd.type != NodeType::Boundary || nd.geomId < 0) continue;
                switch (nd.curveKind) {
                    case CurveKind::Line:   ++nLine; break;
                    case CurveKind::Circle: ++nCircle; break;
                    case CurveKind::Smooth: ++nSmooth; break;
                    default:                ++nPoly; break;
                }
            }
            if (nLine + nCircle + nSmooth > 0) {
                std::cout << "  - Surface curve model  : line=" << nLine
                          << " circle=" << nCircle << " smooth=" << nSmooth
                          << " polyline=" << nPoly << "\n";
                // If a circle segment exists, fit it and report the radius.
                for (const auto& geomData : allGeometries) {
                    if (!geomData.meta.valid) continue;
                    std::vector<Point2D> circPts;
                    for (size_t pi = 0; pi < geomData.points.size(); ++pi) {
                        auto kit = geomData.meta.segKind.find(geomData.meta.segId[pi]);
                        if (kit != geomData.meta.segKind.end() && kit->second == "circle")
                            circPts.push_back(geomData.points[pi]);
                    }
                    if (circPts.size() >= 3) {
                        CircleCurve cc(circPts);
                        if (cc.valid())
                            std::cout << "      * circle fit           : r=" << cc.radius()
                                      << " center=(" << cc.center().x << ", " << cc.center().y << ")\n";
                        break;
                    }
                }
            }
        }

        try {
            lastH = blGen.generate(allBoundaryIds);
        } catch (const std::exception& e) {
            std::cerr << e.what() << std::endl;
            std::cerr << "Proceeding to export partial mesh for debugging..." << std::endl;
            blSuccess = false;
        }

        if (blSuccess) {
            mesh.generateFarFieldGmsh(config, lastH);

            if (config.blSmoothingIters > 0) {
                mesh.smoothMesh(config.blSmoothingIters);
            }
        } else {
            hasIntersection = true; // Use this to trigger return 1 later
        }
    }

    std::cout << "\n[ Mesh Statistics ]\n";
    std::cout << "  - Vertices (VRT)       : " << mesh.nodes.size() << "\n";
    std::cout << "  - Elements (CEL)       : " << mesh.elements.size() << "\n";
    std::cout << "  - Boundary Edges (BND) : " << mesh.edges.size() << "\n\n";

    if (config.exportVTK) {
        std::string vtkFile = outputFilename;
        if (!blSuccess) {
            size_t dotPos = vtkFile.find_last_of('.');
            if (dotPos != std::string::npos) {
                vtkFile.insert(dotPos, "_er");
            } else {
                vtkFile += "_er.vtk";
            }
        } else {
            if (vtkFile.find('.') == std::string::npos) vtkFile += ".vtk";
        }
        mesh.exportVTK(vtkFile);
        std::cout << "Mesh saved to: " << vtkFile << std::endl;
    }
    
    if (config.exportStarCD) {
        std::string starCDPrefix = outputFilename;
        if (starCDPrefix.length() > 4 && starCDPrefix.substr(starCDPrefix.length() - 4) == ".vtk") {
            starCDPrefix = starCDPrefix.substr(0, starCDPrefix.length() - 4);
        }
        mesh.exportStarCD(starCDPrefix, config);
        std::cout << "StarCD mesh saved to: " << starCDPrefix << ".*" << std::endl;
    }

    if (config.exportCGNS) {
        std::string cgnsFile = outputFilename;
        if (cgnsFile.length() > 4 && cgnsFile.substr(cgnsFile.length() - 4) == ".vtk")
            cgnsFile = cgnsFile.substr(0, cgnsFile.length() - 4);
        cgnsFile += ".cgns";
        mesh.exportCGNS(cgnsFile, config);
    }

    return hasIntersection ? 1 : 0;
}
