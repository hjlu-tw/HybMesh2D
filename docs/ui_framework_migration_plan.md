# UI 框架遷移評估與路線（已確認方向，尚未執行）

> **狀態：方向已確認，暫不執行。** 先把 2D 版本調教完，未接到明確指令前不要動工。
> 本文件不會被自動載入；需要時再打開。

## 目標（使用者需求）
1. 3D 前處理的好操作性（互動）
2. 3D 後處理可視化
3. 整體一個完整流程（前處理 → 網格 → 求解 → 結果）
4. 未來可能做成 Web（**明確定調：先桌面、Web 之後再說**）

## 決策：路線 B — pyvistaqt 桌面先行、VTK 為核心、全程 trame-ready
- 桌面用 `pyvistaqt`（VTK 嵌進 Qt），Web 之後用 `trame`（Kitware 的 VTK+Web 全端）。
- 兩者共用同一份 VTK data model 與 pipeline → 桌面現在做、Web 之後接，不必重寫兩次。
- 3D 前處理操作性最好、風險最低、可分階段驗證。
- 既有 Qt-free 服務層（`models/pipeline_config.py`、`services/pipeline_runner.py`、`solver_case.py`、`contour_render.py`）與 `run_pipeline.sh` 無頭流程是最大資產：業務邏輯與 UI 已解耦，換 UI 只需重寫 views 層。

## 為何不選其他路線
- **客製化 ParaView App（C++/Qt + pqApplicationComponents）**：不做 Web；C++ Qt 無法乾淨嵌進 PyQt6；pipeline/server-manager 範式對互動 CAD 編輯不合；建置/打包地獄。出局。
- **ParaView plugin / 巨集**：產品變成「寄生在 ParaView」，受限其 UX，pvpython 直譯器混用痛。與自有 GUI 投資方向不符。
- **trame 現在就上（Web-first）**：只有在 Web 是近期明確目標時才值得；使用者已定調先桌面，故不現在做（避免先寫 PyQt6 再全丟重寫）。

## ParaView 能不能做前處理？（釐清）
- **能做的**：本質是 VTK filter 的幾何/網格變換 — Clip、Slice、Transform、Extract Surface、Threshold、Decimate、Smooth、Subdivide、Triangulate、Extrusion、Generate Normals、Append 等。
- **不能做的（正是核心護城河）**：不是網格產生器、不是 CAD 編輯器 — 無 CFD 網格生成、**無邊界層(BL)生成**、無 hybrid quad/tri、無互動 CFD 屬性指派 UI（per-patch BC / per-patch BL / refinement）、逐頂點 CAD 編輯幾乎沒有。
- **關鍵洞察**：ParaView 能做的那些 filter 全是 VTK 的，`pyvista` 直接就有 → 走路線 B 就「白拿」，不需要為它們背整個 ParaView 殼；ParaView 缺的 meshing/BL/CAD 你本來就有（HybMesh2D + Gmsh + resampler）。這與 CFD Support 的分工一致（meshing 用 OpenFOAM，ParaView 只做後處理視覺化）。

## 分階段路線圖（等 2D 穩定後才啟動）
- **Phase 0 — Spike（約 1 週）**：把 `stl3d_canvas.py`（現用 `pyqtgraph.opengl`）換成 `pyvistaqt.QtInteractor` QWidget。驗收：大檔載入時間、旋轉/縮放流暢度、硬體 picking、macOS 多一組 VTK dylib 的打包複雜度（沿用 `run.sh` 的 `DYLD_LIBRARY_PATH` 模式）。
- **Phase 1 — 3D 前處理操作性**：VTK 硬體 picking 做「選面/patch → 指定 BC / per-patch BL / refinement / transform」。**範圍限縮在「實體選取 ＋ 屬性指派」，不做 3D 逐頂點 CAD（最大風險點）。**
- **Phase 2 — 3D 後處理**：`result_canvas.py` / `mesh_canvas.py` 換 VTK；contour / clip / slice / streamline / glyph / warp 免費拿；大網格 GPU 渲染解效能天花板。
- **Phase 3 — Web（trame，之後才啟動）**：只重寫外殼 views → trame 前端；資料/渲染已在 VTK、邏輯已在 Qt-free 層，成本大降。

## trame-ready 的三條紀律（Phase 0–2 就要守）
1. VTK 場景/pipeline 建構邏輯放進 Qt-free 層，views 只負責渲染與接互動事件（桌面/ Web 共用建構碼）。
2. 不要讓 Qt 型別滲進前後處理邏輯；選取狀態/picking 結果用純資料結構表達。
3. 互動事件走「語義意圖」（如 `patch_selected(id)`），桌面用 Qt signal 接、Web 用 trame state 接，邏輯層不需知道差別。

## 風險與對策
| 風險 | 對策 |
|---|---|
| macOS 打包多一組 VTK/pyvista dylib | 沿用 `run.sh` 的 `DYLD_LIBRARY_PATH`；Phase 0 就先驗打包 |
| VTK 學習曲線（mapper/actor/picker） | 比 ParaView server-manager 淺；先用 PyVista 高階 API |
| 3D 逐頂點編輯被期待但難做 | 3D 前處理限縮在實體選取＋屬性；逐點 CAD 留在 2D |
| 2D 編輯器要不要一起換 | **不要**——`canvas.py` 的 2D 選點/切段 pyqtgraph 很稱職，維持現狀 |

## 排序約束（重要）
- **優先把 2D 版本調教完**；不要在還會晃動的地基上開始重寫。
- 路線 B 是增量且刻意不碰 2D 編輯器，「調教 2D」與「未來導入 VTK」不在同一程式路徑、不衝突。
- 現在唯一「免費」該持續做的：維持既有 Qt-free 服務層紀律（成本為零，對 2D 穩定與未來 3D/Web 都有利）。其他 VTK/trame 規劃先擱著。
