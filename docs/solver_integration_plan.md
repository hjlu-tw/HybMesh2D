# HybMesh2D → Solver → 後處理：完整實施計畫（統整版）

> 本文件統整 `plan_a_implementation.md` 與 `architecture_recommendations.md`，並納入後續討論的所有決策，為 solver 整合的單一事實來源（single source of truth）。

---

## 0. 已定案的關鍵決策

| # | 決策 | 理由 |
|---|------|------|
| D1 | **留在現有 repo**，採方案 A（漸進式擴展），不動既有 import 路徑 | pipeline 是一條完整工作流；GUI 已有 controller→worker→binary 模式與 mode/canvas stack |
| D2 | **可視化只做 2D（e2d）** | solver 輸出為 2D FETRIANGLE + cell-centered；3D 暫不需要 |
| D3 | **Results 畫布用 matplotlib 內嵌**，移除 pyvista/pyvistaqt | 需要流線：`tricontourf`+`streamplot`+`quiver` 全原生，開發最快、品質高 |
| D4 | **bDecompose 設計成可選旁路**，主線預設 `getPGrid → unicones` | 實際 `solver/run.sh` 跳過 bDecompose，unicones 走 pthread 非 MPI |
| D5 | **getPGrid / bDecompose 先跳過編譯，直接用現成 binary** | `solver/preprocess/{getPGrid,bDecompose}/work/` 下已有可用 binary |
| D6 | **solver_ctrl 負責建立 case 工作目錄、改名、改寫 input.in 路徑** | solver 對 CWD/相對路徑/固定輸出檔名高度依賴；getPGrid 輸出名與 solver 需求名不同 |
| D7 | **非 IBM case 略過 DLL 編譯；IBM 模式才加 g++ 編譯步驟** | IBM case 需把 `.cc` 編成 `.so`（init_cond / motion DLL） |
| D8 | **residual 監控格式待裸跑確認**（R1） | solver 可能寫 convergence file 而非 stdout；Phase 4.2 做法依裸跑結果決定 |

---

## 1. 既有架構（沿用，不更動路徑）

```
tools/PreProcessor/gui/app/
├── controller.py            # 頂層 orchestrator + undo/redo（已 ~30KB，新邏輯放獨立 ctrl）
├── controllers/             # mixin 模式：segment / session / backend / mesh_gen / curve / transform / open_endpoint
├── models/                  # segment / project / mesh_config / session / vtk_mesh
├── views/
│   ├── canvas.py            # 幾何畫布 (pyqtgraph)
│   ├── mesh_canvas.py       # 網格畫布 (pyqtgraph, 已有 per-element 填色邏輯)
│   ├── main_window.py       # mode_combo + sidebar_stack + canvas_stack
│   └── panels/
├── workers/                 # backend_run.py / mesh_gen_run.py (QThread 範本)
├── services/  commands/  styles.py  utils.py
```

> 整合策略：**複製 `mesh_gen_run.py` 的 worker 模式** + Results 畫布改用 matplotlib（D3）。

---

## 2. 實際 Solver Pipeline（已驗證的格式相容性）

```
PreProcessor (resample)  →  HybMesh2D (mesh gen)
                                  │  .vrt / .cel / .bnd  (STAR-CD)
                                  ▼
                            getPGrid  (互動式，stdin 餵 para.in)
                                  │  .grid / .bc  (stifcons 格式)
                    ┌─────────────┴──────────────┐
            (可選旁路 D4)                      (主線)
            bDecompose (MPI 分區)                │
                    └─────────────┬──────────────┘
                                  ▼
                            unicones.eqn6.mac  (pthread，-t .autotest input.in)
                                  │  Tecplot FEBLOCK .dat
                                  ▼
                            Results  (matplotlib: contour + streamline + vector)
```

**已實測相容**：
- HybMesh2D `.bnd` = `idx v1 v2 0 0 groupId 0 name`（8 欄），與 getPGrid 輸入完全一致
- HybMesh2D `.vrt` 格式與 getPGrid 輸入一致
- getPGrid/bDecompose 互動輸入 = `para.in` 逐行餵 stdin
- Tecplot 輸出：`DATAPACKING=BLOCK`、`ZONETYPE=FETRIANGLE`、變數 `x,y,ρ,u,v,T,p,M,vort,phi`、`VARLOCATION([1-2]=NODAL,[3-10]=CELLCENTERED)`

**待裸跑確認**：unicones 的 stdout/收斂輸出格式（R1）、實際產生的檔案清單。

---

## 3. 新增 / 修改檔案清單

### 🆕 新增（8）
| 檔案 | 用途 |
|------|------|
| `app/models/solver_config.py` | Solver pipeline 設定模型 + 產生 `input.in` / `para.in` / `bc.def` |
| `app/models/result_data.py` | Tecplot FEBLOCK 解析 + `cell_to_node()` helper |
| `app/workers/solver_run.py` | QThread：getPGrid →（bDecompose 可選）→ unicones |
| `app/controllers/solver_ctrl.py` | case 目錄建立 / 改名 / input.in 改寫 / 啟停監控 |
| `app/controllers/postprocess_ctrl.py` | 結果可視化控制（變數 / colormap / clim / 流線開關） |
| `app/views/panels/solver_config_panel.py` | Solver 參數面板 |
| `app/views/panels/solver_monitor_panel.py` | pipeline 進度 + 收斂監控 |
| `app/views/result_canvas.py` | matplotlib 內嵌結果畫布 |

### ✏️ 修改（4）
| 檔案 | 內容 |
|------|------|
| `app/controllers/__init__.py` | 匯入 `SolverControllerMixin`, `PostprocessControllerMixin` |
| `app/controller.py` | 繼承新 mixin + 初始化 `global_solver_config` / `global_result_data` |
| `app/views/main_window.py` | mode_combo 加 "Solver" / "Results"；sidebar_stack / canvas_stack 加新頁 |
| `app/utils.py` | `find_solver_executables()` 指向現成 binary（D5），不做編譯 |

---

## 4. Phase 設計

### Phase 1 — 資料模型

**1.1 `solver_config.py`**（dataclass）
- Pipeline 路徑：`getpgrid_binary` / `bdecompose_binary` / `solver_binary`（預設指向 `solver/.../work/` 現成 binary，D5）
- getPGrid 輸入：`input_vrt/cel/bnd_file`、`is_3d=False`、輸出 `output_grid/bc_file`
- **bypass 旗標**：`enable_decompose=False`（D4），`num_partitions`
- Solver 參數（對應 `input.in`）：`domain_type='e2d'`、`fs_mach`、`fs_tinf`、`fs_unit_re`、`linf`、`prandtl`、`alpha`、`beta`、`dissip_ctrl`、`epsilon`、`cfl`、`constant_cfl`、`num_half_iter`、`print_convg_per_niter`、`print_sol_per_niter`、`apply_pthread`、`max_nthread`、`num_zones_per_block`
- IBM（D7）：`immersed_solid=False`、`solid_phase_phi_min`、`init_cond_dll`、`motion_dll`（為 `.cc` 原始碼路徑，IBM 時編譯）
- BC：`bc_definitions = [{"segment_no":33,"bc_type":5}, ...]`
- `work_dir`、`case_name`
- 方法：`generate_input_in()` / `generate_getpgrid_para()` / `generate_bdecompose_para()` / `generate_bc_def()` / `save/load`

**1.2 `result_data.py`**
- 解析 Tecplot FEBLOCK：`variables` / `nodes(N,2)` / `elements(E,3)` / `cell_data{var:array(E,)}` / `zones[]`
- **`cell_to_node(var)`**：把 cell-centered 場平均到節點（流線與平滑 contour 共用，R6）
- 逐 zone 惰性載入（R7）
- ❌ 不做 `to_pyvista_mesh()`（D3）

### Phase 2 — Worker `solver_run.py`
模仿 `mesh_gen_run.py`：
- signals：`log_signal` / `progress_signal(0..100)` / `stage_signal` / `residual_signal(dict)` / `finished_signal(rc)`
- `_run_getpgrid()`：`subprocess.Popen(stdin=PIPE)` 餵 `para.in` 內容（互動式）
- `_run_bdecompose()`：**僅當 `enable_decompose`**（D4）
- `_run_solver()`：`unicones -t .autotest input.in`，**cwd 設為 case work dir**（D6）；即時解析 stdout
- `_parse_solver_output()`：**格式依裸跑結果填入**（R1/D8）；若 solver 只寫 convergence file，改為輪詢檔案
- `cancel()`：terminate 當前 process

### Phase 3 — Controller

**3.1 `solver_ctrl.py`**（最關鍵，D6 工作量集中於此）
- `prepare_case_dir()`：建立 `case/<name>/{work,grid,dll}`，把 getPGrid 輸出 **改名**（`mesh_cartesian.grid/.bc` → `<name>.grid/.bc`）放到 `grid/`
- `rewrite_input_in()`：產生 `input.in`，把 grid/bc/DLL 路徑改寫成相對 work dir
- `compile_ibm_dll()`：**僅 IBM 模式**（D7），g++ 把 `.cc` 編成 `.so`
- `_auto_link_mesh_output()`：自動接 HybMesh2D 的 `.vrt/.cel/.bnd`
- `run_solver_pipeline()` / `cancel_solver()` / `_on_solver_*` 回呼
- `_find_solver_executables()`：用現成 binary（D5）

**3.2 `postprocess_ctrl.py`**
- `load_result(path)` / `change_variable()` / `update_colormap()` / `update_clim()` / `toggle_mesh_overlay()` / `toggle_streamlines()` / `export_screenshot()`

### Phase 4 — View

**4.1 `solver_config_panel.py`**：可折疊區塊（Pipeline 路徑 / 網格轉換 / 流場條件 / 數值 / 迭代 / 平行 / IBM / BC 映射）+ Run/Cancel；含 **"Enable domain decomposition" 勾選**（D4）

**4.2 `solver_monitor_panel.py`**：pipeline stage 進度 + 收斂監控（pyqtgraph 即時曲線）。**實作方式待 R1 裸跑確認**：stdout 可解析則即時 emit；否則輪詢 convergence file。

**4.3 `result_canvas.py`**（matplotlib 內嵌，D3）
- `FigureCanvasQTAgg` + `NavigationToolbar2QT`，深色主題對齊 `styles.py`
- `Triangulation(x,y,elements)`（快取）
- contour：cell-centered → `tripcolor(shading='flat')`；平滑 → `cell_to_node` + `tricontourf`
- **流線**：`cell_to_node(u)`,`cell_to_node(v)` → `LinearTriInterpolator` → 規則 meshgrid 取樣 → `streamplot`（R6）
- 向量：`quiver`（降採樣）；網格疊加：`triplot(lw=0.2)`
- colorbar：`fig.colorbar`

### Phase 5 — 主視窗整合
- `mode_combo`：加 "Solver"(3) / "Results"(4)
- `sidebar_stack`：加 solver_config_panel(3) / solver_monitor_panel(4)
- `canvas_stack`：加 result_canvas(2)
- `_on_mode_changed` canvas_map：`{0:0,1:1,2:1,3:1,4:2}`
- `controller.py`：繼承兩個新 mixin + 初始化 state

---

## 5. 依賴

```
# 已安裝，無需新增重量級依賴：
# matplotlib 3.9.4   (Results 畫布 + 流線)
# pyqtgraph 0.13.7   (solver monitor 即時曲線)
# numpy 2.0.2
# ❌ 移除 pyvista / pyvistaqt（D3）
# matplotlib.backends.backend_qtagg 為內建，免裝
```

---

## 6. 實作順序

| 序 | Phase | 工時 | 說明 |
|----|-------|------|------|
| 0 | **裸跑驗證** | 0.5h | 跑 getPGrid + unicones，抓 stdout/收斂格式（消 R1/R2） |
| 1 | Phase 1 | 1-2h | 資料模型（無 UI 依賴） |
| 2 | Phase 2 | 2-3h | Worker（含 stdin 餵 para.in） |
| 3 | Phase 5（部分） | 1h | mode combo + canvas stack |
| 4 | Phase 4.1 | 2-3h | solver config panel |
| 5 | Phase 3.1 | **4-5h** | solver controller（case 目錄/改名/改寫，D6 工時加倍） |
| 6 | Phase 4.2 | 1-2h | solver monitor（依 R1 結果） |
| 7 | Phase 1.2 | 2h | Tecplot parser + cell_to_node |
| 8 | Phase 4.3 | **4-5h** | result canvas（contour + 流線，含 cell→node） |
| 9 | Phase 3.2 | 1-2h | postprocess controller |
| 10 | Phase 5（完成） | 1h | toolbar/mode 連接 |

---

## 7. 風險登記（持續追蹤）

| # | 風險 | 狀態 / 緩解 |
|---|------|------------|
| R1 | residual stdout 格式未知 | **裸跑確認中**；否則改輪詢 convergence file |
| R2 | pipeline 順序（bDecompose） | ✅ 已決議：可選旁路（D4） |
| R3 | CWD/目錄結構依賴 | ✅ 由 solver_ctrl 負責（D6），工時已加倍 |
| R4 | getPGrid/bDecompose 編譯 | ✅ 用現成 binary（D5） |
| R5 | IBM DLL 編譯 | ✅ 僅 IBM 模式編譯（D7） |
| R6 | 流線需 cell→node | ✅ `result_data.cell_to_node()` |
| R7 | 大型 transient 載入 | 逐 zone 惰性載入 |
| R8 | matplotlib 互動性中等 | 已接受取捨；必要時 contour 退回 pyqtgraph |
| R9 | `print_convg_per_niter` 預設 10 萬，即時監控無資料 | ✅ 裸跑發現；solver_config 預設小值（100）並在面板標註（見 8.3） |

---

## 8. 裸跑驗證結果（2026-06-18 實測）

### 8.1 getPGrid（R2 stdin 機制）✅ 通過
- `./getPGrid < para.in` → exit 0，產出 `mesh_cartesian.grid` / `.bc` / `.bc.def`
- 確認互動式程式可用 `Popen(stdin=PIPE)` 餵 para.in 全文，逐行對應 prompt
- 現成 binary（arm64）可直接用，無需重編（D5 成立）

### 8.2 unicones（R1 收斂格式）✅ 通過 — **收斂有印到 stdout，格式可解析**
- 從 case work dir 執行（cwd=work），relative path `../grid/SQ.grid`、`../dll/*.so` 正確解析（**確認 D6：必須以 work dir 為 cwd**）
- 讀入 50426 nodes / 99994 elements / 858 boundary elements，pthread 平行，**未用 bDecompose / mpirun**（確認 D4 旁路設計）
- **stdout 每個收斂輸出區塊格式**：
  ```
  Global Iteration count <N> :
   cfl = <val>
   physical time = <val>
   eL2 error norm for int.  region =   <r1> <r2> <r3> <r4> <r5>   ← 每個 zone 一行（本 case 30 行）
   ...
   eL2 error norm of bound. region =   <b1> <b2> <b3> <b4> <b5>   ← boundary 一行
  ```
  5 個數值 = 5 個守恆量殘差（連續/x-mom/y-mom/能量/第 5 項）。多 zone → 繪圖時需聚合（取 max 或加總）。
- 同時寫一個收斂檔 `<base>.enorm.<tag>`（本次 0-byte，因未達列印間隔）
- `-t <tag>` 參數決定輸出檔尾綴；輸出檔：`xtecp_sol_allz.dat.<tag>`（Tecplot 解，受 `print_sol_per_niter` 控制）、`tWall_values.dat`、`vsurface_qty.dat`、`unicones.enorm.<tag>`、`WallForce.dat`

### 8.3 新增關鍵約束 → R9
- `input.in` 的 **`print_convg_per_niter` 預設 100000** → 收斂資訊每 10 萬次迭代才印一次。
- 裸跑時只看到 `Global Iteration count 0` 一個區塊（之後靜默計算）。
- **即時 residual 監控必須把 `print_convg_per_niter` 設小（如 100）**，否則 monitor 面板長時間無資料。
- 同理 `print_sol_per_niter`（預設 500000）控制 Tecplot 輸出頻率，影響 Results 何時有檔可看。

### 8.5 全鏈路測試（Phase 5 收尾，2026-06-18）
實跑 getPGrid + unicones（mesh_cartesian、非 IBM、30 迭代）→ 監控 → Results 渲染，全程通過：
- getPGrid 產 grid/bc/companion ✅；unicones 跑出 2.1MB Tecplot ✅
- residual 擷取 3 筆（iter 0/10/20）、監控 4 曲線、Results 自動載入並渲染出真實 Mach 流場 + 流線 ✅

**測試中發現並修正的兩個真實問題**：
1. **segment 表位置**：solver 從 cwd(work) 讀 `<bc>.def` companion（getPGrid 產在 grid/）。→ worker 在 getPGrid 後把 companion 複製到 work（使用者覆寫存在時不蓋）。
2. **stdout 格式有兩種**：IBM run 有 `Global Iteration count` 標頭且 eL2 為 5 欄；非 IBM run **無該標頭**且 eL2 為 4 欄。→ parser 改用 **`bound. region` 行作為一次收斂輸出的終結分隔**，iter 號用顯式標頭否則合成計數（步進 print_convg_per_niter），分量數動態。兩格式皆相容。

> 另注意：BC flag `3` 會被 solver 視為需要 DLL 的邊界（非程式 bug，屬資料/設定層）。auto 路徑用 getPGrid companion 的 flag；使用者可用 BC 表覆寫。

### 8.4 對 Phase 4.2 / Phase 2 的確定結論
- **採 stdout 即時解析**（不需輪詢 enorm 檔）。`_parse_solver_output()` 規則：
  - `Global Iteration count (\d+)` → 當前 iter
  - `cfl = ([\d.eE+-]+)` / `physical time = ...`
  - `eL2 error norm for int.  region =\s+(...)` → 收集各 zone 5 值，聚合後 `residual_signal.emit({"iter":N, "L2":[...]})`
  - `eL2 error norm of bound. region =` → 邊界殘差
- solver_config 對 `print_convg_per_niter` 預設給**監控友善的小值**（如 100），並在面板標註。
</content>
