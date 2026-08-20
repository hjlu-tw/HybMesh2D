# 幾何 → 網格 Pipeline 重構計劃

> 目標：把目前「research 級」的 file-based pipeline，逐步補強到「工業級」——
> 核心是把**幾何關聯（geometry association）**帶進 mesher，並讓最終網格能無損交給 solver。
>
> 撰寫日期：2026-06-23 ｜ 分支：`feat/gui-interactive-cad-editing`

---

## 執行狀態（2026-06-23）

| Phase | 狀態 | 摘要 |
|-------|------|------|
| **1** 交接 metadata | ✅ 完成並驗證 | `.dat` 旁寫 line-based `.meta` sidecar（seg_id/is_corner/piece_breaks/seg→bc）；mesher `loadSurfaceMeta` 灌進 `Node.{segId,isCorner,bcTag}`；`exportStarCD` 幾何邊優先用 `bcTag`。缺/不符 sidecar → fallback。CLI 端到端驗證（L-shape 6 corners、bcTag override、naca0012 無 sidecar 仍正常）。GUI 免改（resampler 直寫最終路徑，sidecar 隨行）。 |
| **4** CGNS 輸出 | ✅ 完成並驗證 | `Mesh::exportCGNS`（unstructured zone + 每 BC 一個 BAR_2 edge section + BC_t patch，BCType 對應 wall/inlet/outlet…）。CMake `find_path/find_library` 選用編入、缺則 stub。`EXPORT_CGNS` 貫穿 Config/CLI(`-out_cgns`)/GUI checkbox。naca0012 產出通過 `cgnscheck`（int64 zone dims、3 BC patch）。 |
| **2** Curve + sidecar v2 | ✅ 完成並驗證 | **採輕量方案**(非完整 library 抽取)：新增共享 header `include/Curve.hpp`(Line/Circle/Smooth/Polyline，**用實際輸出點擬合**故 transform-safe)。resampler 從 `curve_type` 推導 kind 寫進 sidecar v2(`seg_id bc curve_kind`)；mesher 解析後灌進 `Node.curveKind`。驗證：圓 r=2 擬合精確(center≈0)、L-shape→smooth+6 corners、Curve.hpp 單元測試(曲率 0.5、切向⊥半徑)、naca 無 sidecar 仍正常。GUI 免改(kind 由既有 curve_type 推導)。per-point t 由 mesher 自點序推導，不需存。 |
| **3** 解析 BL | ✅ 完成並驗證 | `BoundaryLayer.cpp` 在旗標 `BL_USE_ANALYTIC_GEOM`(預設關閉)開啟時，對 **line/circle 段的非角點**用 `makeCurve()` 的精確法向覆蓋初始 `n1/n2`；smooth/polyline 與角點/convex/concave 完全不動。旗標貫穿 Config/print/GUI(mesh_config + BL 區勾選框)。驗證：非均勻圓 19 節點、最大 7.6° 法向修正且網格有效；均勻圓 0 shift(無偽變動)；smooth L-shape 0 override(安全)。**註**：gmsh 遠場三角化為非確定性(同輸入兩跑 VTK 即不同，節點數穩定)，故 A/B 改以確定性的初始法向 telemetry 驗證，而非 VTK diff。 |
| **1b** GUI BC 選擇器 | ✅ 完成並驗證 | CAD 檢視器新增「Boundary:」可編輯下拉(空=繼承全域 BC_GEOM)。`SegmentModel.bc` 欄位 + 序列化；`segment_ctrl.update_segment_bc` 走 `UpdateMultipleSegmentsStateCmd`(undo/redo)，選取時同步、支援多選。驗證:ProjectModel(bc=myinlet)→export_config→resampler→sidecar `1 myinlet circle`，串起 GUI→mesher 全鏈。**註**:「preview 改讀 sidecar 取代 nan」為次要 polish，未做(nan 機制運作正常)。 |

### Phase 1+4 過程中的關鍵發現（重要，影響可攜性）
1. **libgmsh 內含自帶的 32-bit CGNS**：`libgmsh.4.15.dylib` 靜態包了一份 CGNS（匯出 267 個 `cg_*` 符號）。HybMesh2D 同時連 gmsh 與 homebrew libcgns 時，macOS two-level namespace 會依**連結順序**綁定 `cg_*`。必須讓 **libcgns 排在 libgmsh 之前**，否則 `cg_zone_write` 綁到 gmsh 的 32-bit 版本、與我們 64-bit 的 header 不一致，zone 維度寫壞（`cgnscheck` 報 Invalid zone dimensions）。已在 CMakeLists 處理並加註解。
2. **arg-parse 既有 bug**：`main.cpp` 第一輪掃描的 positional 分支會把未識別 value-flag 的值（如 `-out_cgns 1` 的 `1`）當成 config 檔名而覆蓋 `-conf`。已用 `confExplicit` 守衛修正。
3. 此版本 HybMesh2D 對 naca0012 產出**純三角形**網格（VTK 也 0 quads）；CGNS 的 QUAD_4 路徑與 `exportStarCD` 同構但這些案例未觸發。

---

## 1. 背景與問題定位

目前 pipeline 為三段、以暫存檔串接的獨立 process：

```
GUI 編輯 ──JSON config──► surface_resampler ──resampled.dat──► HybMesh2D ──.vtk──► GUI
```

經程式碼盤點，確認兩個根本弱點（不是「用檔案」本身，而是檔案內容太貧乏）：

| # | 問題 | 證據（程式碼位置） | 後果 |
|---|------|------|------|
| P1 | 交接格式 lossy：只有 `x y` | `tools/PreProcessor/src/main.cpp:96` `saveGeometry()`；`src/main.cpp:11` `loadGeometry()` | 丟失「點屬於哪段 / 哪個 BC / 是否 corner」 |
| P2 | 解析曲線在進 mesher 前就被 bake 成死點 | `generateCurvePoints()` `tools/PreProcessor/src/main.cpp:201-364` 立即離散化，不保留 `Curve` 物件 | mesher 無法回查真實曲率/法向，BL 只能用有限差分近似 |
| P3 | BC 用「離 domain box 多近」反推 | `src/Mesh.cpp:305-316`（`exportStarCD`）以座標 proximity 分類 group | 多 body / 內部邊界時容易誤判；無法 per-segment BC |
| P4 | preview 用 `nan nan` 列當分隔 hack | `saveGeometry()` `tools/PreProcessor/src/main.cpp:121-122` | 格式表達力不足的徵兆 |
| P5 | 最終輸出無拓樸/zone 資訊 | `exportVTK` `src/Mesh.cpp:138`（無 BC）；STAR-CD group 靠 proximity | 與 solver 互通需人工補資訊 |

**已具備的有利條件：**
- 兩個 binary 已共用 `include/GeomUtils.hpp`（透過 `HybMeshUtils` INTERFACE lib，`CMakeLists.txt`）。
- `HybMesh2D` 已 **in-process 連結 Gmsh SDK**（`src/Mesh.cpp:4,328`），遠場已有 in-memory 幾何模型——只有「輸入表面」是死點，屬於不對稱、好補。
- resampler 內部其實已用 `ResampleTask`（`tools/PreProcessor/src/main.cpp:378-385`）追蹤每段邊界，metadata 早就算得出來，只是沒寫出去。

---

## 2. 設計原則

1. **加法式、可向後相容**：每一步都不破壞既有 `.dat` / JSON config / CLI 用法；新欄位缺省時走舊行為。
2. **保留 process 邊界的好處**：crash isolation、headless 可重現、CLI 可單獨測試——這些不丟。檔案交接保留，只是讓它**無損**。
3. **幾何關聯是核心**：讓「真實曲線定義」活過離散化，mesher 需要時能回查。
4. **每階段獨立可交付、可驗證**：用既有範例幾何（`naca0012`、letters、circle）做 regression。

---

## 3. 階段總覽與相依

| Phase | 主題 | 對應建議 | 風險 | 相依 | 建議順序 |
|-------|------|---------|------|------|---------|
| **1** | 豐富交接格式（per-point metadata） | 建議①（短期） | 低 | 無 | 先做 |
| **4** | CGNS 輸出（給 solver） | 建議③（互通） | 低-中 | 無 | 可與 1 併行 |
| **2** | resampler 變 library + 保留解析曲線 | 建議②（中期核心） | 中 | 無（但 3 需要） | 接著做 |
| **3** | BL 使用解析法向/曲率/corner | 建議②延伸 | 高 | 需 Phase 2 | 最後 |

> 直覺：**Phase 1 + 4 是低風險快贏**（補欄位、加輸出格式）；**Phase 2 是結構核心**（補回幾何關聯）；**Phase 3 是收割**（最敏感的 BL 程式碼，放最後並加旗標）。

---

## Phase 1 — 豐富交接格式（per-point metadata）

**目標**：讓表面交接檔無損攜帶 `segment id / is-corner / BC tag / 原曲線參數 t`，並用顯式 metadata 取代 `nan nan` hack。

**動機**：直接解 P1、P3、P4。BL 能信任 corner 旗標；BC 改為顯式指派而非 proximity 反推。

**具體變更**
- **格式設計（二選一，建議 A）**
  - **A. 同名 sidecar metadata（推薦）**：`foo.dat` 旁多一個 `foo.meta.json`，內含 `points[]`（每點 `seg_id`, `is_corner`, `bc`, `t`）與 `piece_breaks[]`。`.dat` 本身維持純 `x y`——舊工具完全不受影響。
  - B. 擴充 `.dat` 欄位：`x y seg_id is_corner bc`，首行 `#` header。較緊湊但破壞「純座標」假設。
- **resampler 端**：`saveGeometry()`（`tools/PreProcessor/src/main.cpp:96`）多輸出 metadata；資料源已存在於 `ResampleTask.start_gp_idx/end_gp_idx` 與 `pieceBreaks`。`detectFeaturePoints()`（同檔 `:366`）的結果寫成 `is_corner`。
- **HybMesh2D 端**：
  - `loadGeometry()`（`src/main.cpp:11`）讀 sidecar；缺檔→走舊行為。
  - `Node` 結構（`include/Mesh.hpp:15-21`）新增 `int segmentId = -1; bool isCorner = false; std::string bcTag;`（或用平行 `std::vector` 對應 surface node，避免污染 interior node）。
  - `exportStarCD()` 的 BC 分類（`src/Mesh.cpp:305-316`）改為**優先採用 `bcTag`**，proximity 僅作 fallback。
- **GUI 端**：`backend_ctrl.py` 的 `_on_preview_finished`（`:316`）改讀 `piece_breaks` 顯式分段，逐步淘汰 `nan` 解析；`format_version` +1。

**向後相容**：sidecar 缺檔 = 舊流程；`.dat` 內容不變。

**測試**：`naca0012`、`box_outer`、letters 各跑一次，確認 (a) mesh 結果與舊版逐節點一致（metadata 尚未改變幾何），(b) BC 指派正確。

**風險／工作量**：低 ／ 約 2–3 天。

---

## Phase 4 — CGNS 網格輸出

**目標**：新增 `exportCGNS()`，輸出帶 zone + BC patch 的標準網格，供 Mode 3 Solver 與外部 solver 無損取用。解 P5。

**動機**：這是真正「工業級」的互通一步；VTK/STAR-CD 留著供視覺化與既有流程。

**具體變更**
- 仿 `exportStarCD()`（`src/Mesh.cpp:183-325`）新增 `void Mesh::exportCGNS(const std::string&, const Config&)`。
  - 用 `Node::geomId`（已存在）建立 zone（每個 body 一區 + 遠場）。
  - 用邊界邊拓樸 + Phase 1 的 `bcTag` 建立 BC patch（`BCWall`, `BCInflow`, `BCOutflow`…）。
- **建置**：`CMakeLists.txt` 加 `find_package(CGNS)`／`find_package(HDF5)`，`target_link_libraries(HybMesh2D ... CGNS::cgns)`。`Config.hpp:49-50,128-132` 增 `EXPORT_CGNS` 旗標；GUI `mesh_config.py` 對應 checkbox。
- 注意現有 `CMakeLists.txt` 的 Gmsh 路徑為**硬編碼絕對路徑**（指向特定使用者目錄）——順手改成 `find_library`/變數，避免換機器就壞。

**向後相容**：純新增輸出格式，預設關閉。

**測試**：對小範例輸出 CGNS，用 `cgnscheck` 驗證合法性；若 solver 已可讀 CGNS，端到端跑一次。

**風險／工作量**：低-中（主要是 CGNS API 學習 + 建置鏈）／ 約 3–5 天。

---

## Phase 2 — 把 surface_resampler 抽成 library + 保留解析曲線

**目標**：
1. 把 resampler 核心抽成靜態庫 `libhybresample`，CLI 變薄殼（保留 headless/測試）。
2. 定義 `Curve` 抽象，讓解析曲線定義**活過離散化**；HybMesh2D 取得「點 + 對應 Curve + 參數 t」。解 P2 的前半。

**具體變更**
- **抽庫**：把 `processElement()`（`tools/PreProcessor/src/main.cpp:505`）及 helper（`generateCurvePoints`, `samplePolylinePinned`, `alignEndpoints`, `distributePointsProportionally`…）移到 `tools/PreProcessor/src/Resampler.cpp` + 公開 header `Resampler.hpp`，對外提供：
  ```cpp
  struct ResampleResult {
      std::vector<Point2D> points;
      std::vector<SurfacePointMeta> meta;        // seg_id, is_corner, bc, t（同 Phase 1）
      std::vector<size_t> pieceBreaks;
      std::vector<std::shared_ptr<Curve>> curves; // 每段保留的解析定義
  };
  ResampleResult resample(const json& config, ...);
  ```
- **CLI 薄殼**：`tools/PreProcessor/src/main.cpp` 的 `main()`（`:915`）改為呼叫 `resample()` 後寫檔——行為與輸出不變。
- **Curve 抽象**：新增 `Curve` 介面：`evaluate(t)`, `tangent(t)`, `normal(t)`, `curvature(t)`；實作 `LineCurve / CircleCurve / PolygonCurve / SplineCurve / FormulaCurve`。`generateCurvePoints()`（`:201-364`）重構為「建 Curve → 取樣」，回傳時保留 Curve 與每點 t。
- **CMake**：新增 `libhybresample` target；`HybMesh2D` 連結它（目前 `HybMesh2D` 只連 Gmsh，`CMakeLists.txt:34-41`）。
- **整合（可分兩小步）**：
  - 2a：HybMesh2D 仍吃檔，但連結同一份庫 → 程式碼去重、行為一致。
  - 2b（選配）：GUI 改送**單一合併 config**（segment 定義 + mesh 參數），HybMesh2D 內部 `resample()` 後直接接 BL，消除中間 `.dat` 落地（互動延遲↓）。檔案落地改為 opt-in（debug/repro 用）。

**向後相容**：CLI 與 JSON config 不變；2b 為新增路徑，舊「先 resample 再 mesh」流程保留。

**測試**：抽庫後對 `test_config.json`、`multi_element_example.json` 等既有 config 跑 CLI，輸出需與重構前 **byte-level 一致**（純 refactor 不應改數值）。

**風險／工作量**：中（refactor 面積大但行為可凍結驗證）／ 約 1–2 週。

---

## Phase 3 — BL 使用解析法向 / 曲率 / 精確 corner

**目標**：BoundaryLayer 從「有限差分近似」升級為「向真實 `Curve` 查詢」。解 P2 後半——這是工業 mesher「mesh on geometry」的精髓。

**具體變更**（皆置於旗標 `BL_USE_ANALYTIC_GEOM` 後，預設關閉）
- 法向計算（`src/BoundaryLayer.cpp:84-91`、逐層 `:247-270`）：當該 surface point 有關聯 `Curve` 時，改用 `curve->normal(t)` 取代鄰點差分。
- corner 判定（`:92-99`）：改採 Phase 1/2 的顯式 `is_corner`（曲率不連續），取代角度門檻猜測——直接決定 fan/parallel 策略。
- 曲率自適應（選配）：用 `curve->curvature(t)` 在高曲率處調整層厚/成長率。

**向後相容**：旗標關閉 = 現行行為，逐位元不變。

**測試**：對 `naca0012`（前緣高曲率、後緣尖角）開/關旗標比較 BL 品質（expansion ratio、有無自交）；用 `visualize_dat.py --quality` 與 mesh stats 對照。**這是最敏感的程式碼，務必逐例 A/B。**

**風險／工作量**：高（BL 是核心且脆弱）／ 約 1–2 週 + 充分驗證。

---

## 4. 非目標（本計劃不做）

- 不引入完整 CAD kernel（Parasolid/OpenCASCADE）——2D 自有 `Curve` 抽象已足夠。
- 不把 GUI 與 mesher 合進單一 process——保留語言/crash 邊界。
- 不改寫 Gmsh 遠場流程——只改「表面如何進 mesher」。

## 5. 建議執行順序

```
里程碑 A（快贏，~1.5 週）：Phase 1  ‖  Phase 4
里程碑 B（核心，~2 週）  ：Phase 2（2a 必做、2b 選配）
里程碑 C（收割，~2 週）  ：Phase 3（旗標 + 逐例驗證）
```

每個里程碑結束都應能：build 通過、既有範例 regression 綠燈、向後相容未破。

## 6. 驗證資產（共用）

- 範例幾何：`examples/geometries/`（`naca0012.dat`、letters、`circle_*`、`box_outer.dat`）
- resampler 既有測試 config：`tools/PreProcessor/config/test_*.json`、`multi_element_example.json`
- 視覺化：`tools/scripts/visualize_dat.py --quality`、GUI Mesh Statistics（Mode 2）
- 凍結式驗證：Phase 2 要求純 refactor 輸出 byte-level 一致；Phase 1/3 要求旗標關閉時逐節點一致。
