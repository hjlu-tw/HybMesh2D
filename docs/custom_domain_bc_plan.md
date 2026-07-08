# 自訂計算域外形 + 內部網格 + Per-Segment 邊界條件 實作計畫

> 目標：讓 mesher 從「只能矩形外框 + 外流」擴充到
> **(1) 任意外邊界外形（多邊形 / 圓 / 扇形）、(2) 對 CAD 封閉幾何生成內部網格（內流）、
> (3) 每條線段（含分割後）各自指定邊界條件**。
> 設計對齊 Pointwise / ICEM-Fluent / STAR-CCM+ / COMSOL / Gmsh 的共同模式。
>
> 撰寫日期：2026-07-07 ｜ 分支：`feat/gui-interactive-cad-editing`
> 前置文件：`docs/pipeline_refactor_plan.md`（Phase 1/1b 已把幾何邊 BC 走 `.meta` sidecar 完成）

---

## 執行狀態（2026-07-07）

| Phase | 狀態 | 摘要 |
|-------|------|------|
| **1** 邊界條件下沉到邊 | ✅ 完成並驗證 | `Edge.bcTag`；矩形四邊於 `buildDomainBoundary` 帶 BC；匯出改 `classifyBoundaryBc`（參考線段點在線段上 → `Node.bcTag` → `bcGeom`），移除座標反推死碼；group id 改依 BC 名稱動態配號。回歸 naca0012 矩形（40 inlet/41 outlet/200 wall）；預設同名側正確合併（inlet/outlet/wall 3 群）；STAR-CD 與 CGNS 一致。**行為變更**：group id 由軸向固定 1–5 改為 name-based（各邊 BC 名稱維持正確）。 |
| **2** 自訂外框外形 | ✅ 完成並驗證 | `Config.domainFile` + `DOMAIN_FILE`/CLI `-domain`；`buildDomainBoundary()`（自訂封閉多邊線每段帶 BC，或矩形 fallback，並以 bbox 覆寫 xMin..yMax）；`checkDomainIntersection` 改對實際外框判定；Gmsh loop 依 |面積| 排序（最大=外圈）。驗證：六邊形外框 + per-segment `.meta`（inlet/outlet/farfield×4/wall）、72 點圓形外框皆生成正確。圓/扇形採重取樣多邊線（GUI 端自適應取樣屬 Phase 4）。 |
| **3** 內部網格（內流） | ✅ 完成並驗證 | `Config.internalFlow` + `INTERNAL_FLOW`/CLI `-internal`；`detectGrowthDirection(growMode)` 由 role 決定內/外長取代矩形框判定；`generate(…, growModes)` 逐迴圈傳入；內流時不建外框、最大迴圈=牆(內長)、其餘=島(外長)；`checkGeometriesIntersection` 內流略過包含檢查（環狀域合法）。驗證：方腔 BL 確實內長（節點全在 [-2,2]）、內流牆面 per-segment BC、方腔+中央島環狀流（島為正確的洞）；外流回歸不變。 |
| **4** GUI 工作流 | ✅ 核心完成並驗證 | `MeshConfig` 新增 `internal_flow` + `INTERNAL_FLOW` 序列化；geom role 擴充 `farfield`(→`DOMAIN_FILE`)，`boundary_files`/`domain_file`/`is_farfield` helper；`load/save_to_file` 處理 `DOMAIN_FILE`/`INTERNAL_FLOW`。面板：role combo 新增「Far-field (custom outline)」、新增「Internal Flow」勾選框，接進 get/set_config。驗證：模型 round-trip、面板 offscreen round-trip、GUI 輸出 config 交 C++ 端到端（六邊形 farfield 每側 BC 正確）。per-segment/分割段 BC 沿用既有 edge_props `bc_combo`+`.meta`，外框段一體適用。**未做(次要 polish)**：canvas 依 BC 上色 (4-D)、圓/扇形自適應取樣 UI (4-E)——皆為視覺/便利強化，不影響功能。 |

**示範 fixtures**（`examples/geometries/`）：`hexagon_domain.dat(+.meta)`（外流自訂外框 + 各側 BC）、`square_cavity.dat(+.meta)`（內流牆面 + per-segment BC）、`island_circle.dat`（環狀島）。

---

## 0. 本計畫與既有進度的關係（先讀）

`pipeline_refactor_plan.md` 已完成的部分是本計畫的地基，**不要重做**：

| 已完成（前置） | 效果 | 對本計畫的意義 |
|---|---|---|
| `.meta` sidecar v2（`seg_id bc curve_kind`） | 幾何每段可帶 BC 與曲線類型 | 外邊界只要沿用同一條 sidecar 管線 |
| `Node.bcTag` + `exportStarCD` 幾何邊優先用 `bcTag` | **幾何邊**的 BC 已是「邊自帶標籤」 | 只剩**外邊界邊**仍靠座標反推，需補齊 |
| GUI edge BC 選擇器（`SegmentModel.bc` + undo/redo） | 使用者已能對幾何段選 BC | 外邊界段沿用同一 UI 即可 |
| `Curve.hpp`（Line/Circle/Smooth/Polyline 擬合）+ `BL_USE_ANALYTIC_GEOM` | 圓段可取得精確法向 | 圓形外邊界「多邊線幾何 + 解析法向」混合做法免額外開發 |
| `detectGrowthDirection()` + `growthSign`（`BoundaryLayer.cpp:26-50`） | BL 已能依 loop 走向往內或往外長 | **內流的核心機制已存在**，只需把「in/out 判定」從矩形框測試一般化 |

**本計畫真正要新增的**：外邊界升格為可自訂外形的曲線幾何、內流的生長方向一般化、外邊界邊的 per-segment BC、以及 GUI 工作流。

---

## 1. 設計原則（對齊商業軟體）

1. **外邊界不是特例，它是「一圈封閉曲線幾何」**（Pointwise connector / Gmsh curve / COMSOL edge）。矩形只是預設捷徑。內流 vs 外流只差「這圈是外框還是洞、BL 往哪長」。
2. **BC 是掛在邊上的具名屬性，不從座標算**（STAR-CCM+ Boundary / Fluent Named Selection / Gmsh Physical Group）。座標反推（`x≈xmin`）在非矩形域必然失效，一律改讀邊上的 tag。
3. **BL 往「流體側」長；流體側 = role + loop 走向**。既有 `growthSign` 就是這個開關，把它從「點是否在矩形框內」一般化為「這圈的角色（外框/障礙物）決定流體在內側或外側」。
4. **加法式、可向後相容**：無 domain 幾何 → 退回矩形；無 role → 預設 obstacle（外流）；每一步都不破壞既有 `.dat`/JSON/CLI，並用 `naca0012` 等既有範例做 regression。
5. **圓/扇形一律多邊線 + 自適應取樣**（段長 ≤ far-field 尺寸，弦誤差自動落在三角形解析度以下）；解析弧線列為未來選配，不進主線。

---

## 2. 統一的心智模型

把兩種流態收斂成同一套抽象：**每個封閉邊界 loop 帶一個 role，BL 往流體側長。**

```
外流 (今天):
  ┌─────────────── domain loop (role=farfield, 不長 BL) ───────────────┐
  │                                                                    │
  │        ╭── obstacle loop (role=wall) ──╮   BL 往外長 (growthSign 使  │
  │        │   ← 流體在障礙物「外側」        │   normal 指向障礙物外)      │
  │        ╰──────────────────────────────╯                            │
  │   三角形填在 obstacle-BL-外緣 與 domain loop 之間                    │
  └────────────────────────────────────────────────────────────────────┘

內流 (新增):
  ┌── domain loop (role=wall_internal) ──┐
  │  BL 往「內」長 (growthSign 反向, normal 指向 loop 內部)              │
  │  ┌────── BL 內緣 front ──────┐        │
  │  │   三角形填滿中央核心區       │        │  ← 沒有額外 far-field box;
  │  │  (可再挖 obstacle 洞)      │        │     domain loop 自己就是最外圈
  │  └───────────────────────────┘        │
  └───────────────────────────────────────┘
```

Gmsh 端 `addPlaneSurface(loops)` 以 **第一圈為外邊界、其餘為洞**。目前 loop 收集順序不保證，故本計畫加入「**依面積排序、最大者為外圈**」使兩種流態都穩健（見 §5 Phase 2-C）。

Role 定義（新增 enum，貫穿 Config / .meta / GUI）：

| role | 語意 | BL | 在 addPlaneSurface 的角色 |
|------|------|----|--------------------------|
| `obstacle`（預設） | 外流障礙物 | 往外長 | 洞（hole） |
| `farfield` | 外流遠場外框（矩形或自訂多邊線） | 不長 | 外圈 |
| `wall_internal` | 內流的封閉壁面 | 往內長 | 自身即外圈（無額外 box） |
| `seed` | 加密種子（既有） | 不長 | 不進 loops |

---

## 3. 資料模型改動總覽

### C++
- **`Edge`（`Mesh.hpp`）新增 `std::string bcTag`**：邊界條件下沉到**邊**（角點共用節點無法區分兩側 BC，故必須邊級）。建構時填入，匯出時直接讀。
- **`Config`（`Config.hpp`）**：
  - 新增 `DOMAIN_FILE <path>`（自訂外框幾何；缺省 → 用 `xMin..yMax` 矩形）。
  - 每個 geometry 可帶 `role`（沿用既有 `geom_roles` 概念；C++ 端以 `GEOM_FILE ... role=wall_internal` 或新 key 表示）。
- **`.meta` sidecar 升到 v3**：新增「檔案級 role」與「外框段 BC」欄位（現為段級 `bc`，外框沿用同格式）。
- **`FrontState.growthSign`**：改由 role 決定（見 Phase 3），不再只看矩形框。

### Python GUI
- **`MeshConfig`（`mesh_config.py`）**：`geom_roles` 由 `{boundary, seed}` 擴為 `{obstacle, farfield, wall_internal, seed}`；序列化對應 `DOMAIN_FILE` / `role=`。新增「domain source = rectangle | shape」。
- **`SegmentModel.bc`（`segment.py`）**：已存在，外框段沿用。
- 面板/畫布：見 Phase 4。

---

## 4. 各 Phase 一覽（建議順序）

| Phase | 名稱 | 依賴 | 交付 | 風險 |
|-------|------|------|------|------|
| **1** | 外邊界 BC 下沉到邊（`Edge.bcTag`） | 無 | 匯出不再靠座標反推；groupId 動態化 | 低（有 fallback） |
| **2** | 自訂外框外形（多邊形/圓/扇形，外流） | 1 | `DOMAIN_FILE` 取代矩形；loop 面積排序 | 中 |
| **3** | 內部網格（內流，BL 內長） | 1,2 | role 驅動 `growthSign`；內流三角化 | 中高（BL 方向） |
| **4** | GUI 工作流 | 1-3 | role 選擇、domain 來源、per-edge BC 上色、內外流切換 | 中 |
| **5**（選配） | 解析弧線 / periodic BC / 多區域 | 1-4 | far-field 真弧、扇形週期、多流體區 | 高，非必要 |

---

## 5. 詳細實作

### Phase 1 — 外邊界 BC 下沉到邊（`Edge.bcTag`）

**問題現況**：匯出時用座標反推（`Mesh.cpp` STAR-CD `~318-341`、CGNS `~415-431`）：`x≈xMin → BC_XMIN`，且 `groupId` 寫死 1–5。幾何邊已改讀 `Node.bcTag`（前置完成），**但外框邊仍靠座標**。

**改動清單**

1. `include/Mesh.hpp`：`struct Edge` 增 `std::string bcTag;`（預設空字串）。
2. `src/main.cpp:281-291`（建矩形外框處）：建 4 條邊時直接寫入 `edge.bcTag = config.bcXMin/Max/YMin/Max`。角點節點共用不再承載 BC。
3. `src/Mesh.cpp` 匯出（STAR-CD + CGNS + VTK）：
   - BC 解析優先序改為 **`edge.bcTag`（非空）→ `Node.bcTag`（幾何段，前置已有）→ 幾何座標反推（僅矩形相容 fallback）→ `bcGeom`**。
   - `groupId` 改為 `std::map<std::string,int>`，依「首次出現順序」動態配號（保留 1–5 給矩形四邊以維持既有輸出對照）。
4. VTK 匯出補上 BC 資訊（前置文件標記 `exportVTK` 無 BC 為弱點 P5），至少以 cell/edge data 帶出 BC id，供 `visualize_dat.py` 上色。

**相容性**：矩形案例在建構時就把四邊 tag 成 `bcXMin..bcYMax`，輸出與今日逐位元相同。座標反推僅保留為 fallback。

**驗證**：`naca0012` 外流（矩形）→ `.bnd`/`.vtk` 與改動前 diff 為空（BC 名稱、group 對照一致）。

---

### Phase 2 — 自訂外框外形（多邊形 / 圓 / 扇形，仍為外流）

**目標**：外框可為任意封閉多邊線；圓/扇形以自適應取樣多邊線表示。

**改動清單**

**2-A　Config / 輸入**
- `include/Config.hpp`：`loadFromFile` 新增 `DOMAIN_FILE <path>`（存入新欄位 `std::string domainFile`）。`print()` 對應顯示。
- 語意：有 `domainFile` → 用它當外框；否則用 `xMin..yMax` 建矩形（今日行為）。

**2-B　main.cpp 外框建構**
- `src/main.cpp:281-291`：抽成 `buildDomainBoundary(mesh, config)`：
  - 無 `domainFile` → 建矩形（現行邏輯），四邊 tag `bcXMin..bcYMax`。
  - 有 `domainFile` → 載入其多邊線（closed），逐段建 `Edge`，每段 `bcTag` 由其 `.meta` 段級 BC 決定（無則 `bcGeom` 或使用者指定的外框預設 BC）。節點型別為 `Boundary`（外流時外框不長 BL）。

**2-C　Gmsh loop 排序（穩健性）**
- `src/Mesh.cpp:556-600`：loop 偵測後，**計算每個 loop 的有向/絕對面積，依絕對面積由大到小排序**，最大者放 `loops[0]`（外圈），其餘為洞，再 `addPlaneSurface(loops)`。任意外框形狀與內流皆穩健。

**2-D　圓/扇形表示（GUI 端，走既有 curve 系統）**
- GUI 既支援 `curve_type = circle / polygon`；扇形 = 弧段 + 兩條徑向邊組成的封閉 polyline。
- **自適應取樣**：resample 段長 ≤ `farFieldSize`（`N ≈ 2πR / h_farfield`）。理由：弦誤差 `e/s = π/(4N)`，段長 ≤ 三角形尺寸時 facet 隱沒於網格解析度以下（見圓/扇形分析結論）。
- 圓段可另開 `BL_USE_ANALYTIC_GEOM` 取得精確近壁法向（若該圓是壁面而非遠場）。

**相容性**：`domainFile` 未提供時完全走舊路徑。loop 面積排序對「外框恆為最大 loop」的既有案例結果不變。

**驗證**：
- 多邊形外框（六邊形）外流繞 `naca0012`，三角化填滿、BC 依段帶出。
- 圓形外框：N 由 `farFieldSize` 自動推得，量測 facet 誤差 < 局部網格尺寸。

---

### Phase 3 — 內部網格（內流，BL 往內長）

**核心洞察**：機制已在，只需把方向判定一般化。

**現況**：`BoundaryLayer.cpp:26-50 detectGrowthDirection()` 以 shoelace 判 `isCCW`，再用 `isInside(p0)`（**對矩形框** `xMin..xMax` 測試）決定 `growthSign`。`growthSign` 貫穿：初始法向（`:84-91`）、逐層重算（`:290-298`）、convex/concave 判定（`:92-98`，公式含 `growthSign`）、解析法向（`:108-142`）。marching 一律 `pos + dir*h`，方向正負已包在 `growthSign` 內。

**改動清單**

**3-A　growthSign 一般化**
- 將 `detectGrowthDirection` 的判據從「`isInside(p0)` 對矩形框」改為 **role + loop 走向**：
  - `obstacle`：流體在 loop **外側** → 維持今日行為（CCW→往外）。
  - `wall_internal`：流體在 loop **內側** → `growthSign` 取反 → normal 指向 loop 內部，BL 往內長。
- 作法：`FrontState` 增 `role` 欄位；`detectGrowthDirection` 依 role 回傳符號（不再依賴 `m_config.xMin..`）。矩形/外流案例 role 預設 `obstacle`，值不變。

**3-B　內流的三角化外圈**
- 內流無額外 far-field box：`domainFile`（role=`wall_internal`）自身即最外圈；BL 往內長後，**BL 內緣 front** 成為三角化區域的外邊界。§5 Phase 2-C 的「面積最大 = 外圈」排序自動選到 BL 內緣（它是剩餘最大 loop）。
- 可選：內部再放 `obstacle`（島嶼）→ 成為洞，形成環狀內流域。

**3-C　角點處理驗證**
- convex/concave 公式已含 `growthSign`（`:92-98`），符號翻轉時分類自動對調；需以內凹/外凸測例確認 fan/merge 行為正確（凹角在內流變成朝流體的凸出，反之亦然）。

**相容性**：role 預設 `obstacle`；未提供 role 的舊 `.meta`/config 完全走外流舊路徑。`isInside` 矩形測試保留為「role 未指定且有矩形框」時的 fallback，確保零回歸。

**驗證**：
- 封閉多邊形（方腔）內流：BL 貼壁往內長、中央三角化、無自交。
- 圓形管道內流 + 中央圓柱島（環狀域）：兩圈 BL 方向相反、洞正確。
- 回歸：`naca0012` 外流 BL telemetry（初始法向）與改動前一致。

---

### Phase 4 — GUI 工作流

**改動清單**

**4-A　role 選擇（`mesh_config_panel.py` + `mesh_config.py`）**
- geometry 清單的 role combo 由 `{boundary, seed}` 擴為 `{obstacle, farfield, wall_internal, seed}`。
- `MeshConfig.geom_roles` 序列化：`farfield`/`wall_internal` → 寫 `DOMAIN_FILE` + `role=`；`obstacle` → `GEOM_FILE`；`seed` → `SEED_FILE`（既有）。

**4-B　Domain 來源選擇（`mesh_config_panel.py`）**
- 現有 4 個 domain spinbox + 4 個 BC widget 保留為 **「矩形快捷預設」** 群組。
- 新增「Domain source」單選：`Rectangle`（用 spinbox）｜`Use drawn shape`（從幾何清單挑一個 role=farfield/wall_internal 的圖形）。
- 內外流切換即由 role（`farfield`=外流、`wall_internal`=內流）表達，不需另一個開關。

**4-C　外框 per-segment BC（沿用既有）**
- 外框幾何的段沿用 `edge_props_panel.py` 的 `bc_combo` + `segment_ctrl.update_segment_bc`（已支援 undo/redo、多選、`.meta` 下傳）。
- 「分割線段設不同 BC」：既有 `split_cmds` 分割 + per-segment `bc` 直接可用，外框段一體適用。

**4-D　畫布 BC 上色（`canvas.py`）**
- 依每段 `bc` 上色（`BCWidget` 已有色標概念），對齊 COMSOL/Pointwise 的視覺回饋。未指定 BC 的段用中性色。

**4-E　圓/扇形自適應取樣 UI**
- 圓/扇形 curve 的取樣點數提供「Auto（≤ far-field 尺寸）」選項，避免使用者手調 N。

**驗證**：GUI 畫一個五邊形設 role=farfield、逐邊設不同 BC、匯出 config + `.meta` → CLI 跑通 → `.bnd` 各 patch 名稱正確；畫方腔設 role=wall_internal → 內流網格生成。

---

### Phase 5 —（選配，非主線）

- **解析弧線**：far-field 以 `gmsh::addCircleArc` 取代多邊線（需把圓心/半徑 metadata 貫穿 BL 前處理與碰撞，工程量大；僅在需要「少點且無 facet 的光滑壁」時考慮）。
- **Periodic BC**：扇形兩條徑向邊配對（葉柵/旋轉機械）；需 BC 型別擴充 + Gmsh periodic 或 solver 端配對。
- **多流體區域**（COMSOL/STAR-CCM+ regions）：多個 `addPlaneSurface` + 各自 physical group。

---

## 6. 風險與相容性總表

| 風險 | 緩解 |
|------|------|
| 移除座標反推破壞既有 `.bnd` | 矩形四邊建構時即 tag `bcXMin..bcYMax`；座標反推保留為 fallback；naca0012 diff 驗證 |
| loop 面積排序改變既有外流結果 | 外流外框恆為最大 loop，排序後仍居首，結果不變；加回歸測 |
| `growthSign` 一般化回歸外流 BL | role 預設 `obstacle`；`isInside` 矩形測試保留為 fallback；BL 初始法向 telemetry A/B |
| 圓 facet 影響精度 | 自適應取樣（段長 ≤ far-field 尺寸）；`e/s=π/(4N)` 保證隱沒於網格解析度 |
| `.meta` v3 與舊 sidecar | 版本號守衛；缺欄位走預設 role=obstacle |
| Gmsh 遠場三角化非確定性（前置文件已知） | 驗證改用確定性指標（初始法向、節點數、BC patch 數），不做 VTK 逐位元 diff |

---

## 7. 測試計畫

**回歸（必須零變動或等價）**
- `naca0012` 外流矩形：`.bnd`/`.vtk` BC 對照、BL 初始法向 telemetry。

**新功能**
1. 六邊形 far-field 外流繞翼型（Phase 2）。
2. 圓形 far-field，N 自動（Phase 2）。
3. 方腔內流（Phase 3）。
4. 圓管 + 中央圓柱島環狀內流（Phase 3）。
5. 外框逐邊不同 BC + 分割段 BC（Phase 1+4）。
6. 扇形域，徑向邊 wall、弧 farfield（Phase 2）。

**工具**：`visualize_dat.py --quality`（expansion ratio）、GUI mesh_canvas、`.bnd` patch 檢視、（若 CGNS）`cgnscheck`。

---

## 8. 建議動工順序

```
Phase 1 (Edge.bcTag)  ──►  Phase 2 (自訂外框, 外流)  ──►  Phase 4 之 4-A/4-B/4-C/4-D (GUI 支援 1+2)
                                                              │
                                                              ▼
                                                   Phase 3 (內流)  ──►  Phase 4 之 4-B role=wall_internal 打磨
                                                              │
                                                              ▼
                                                        Phase 5 (選配, 視需求)
```

理由：Phase 1 是所有匯出正確性的前提且風險最低；Phase 2 讓「自訂外形」先在外流可用、可視覺驗證；GUI 先補到能操作 1+2；Phase 3 內流是最大概念跳躍，放在資料模型與外框都穩定後再做，回歸面最小。
