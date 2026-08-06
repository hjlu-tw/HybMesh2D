# HybMesh PreProcessor GUI — 改善計劃與 Checklist

> 目的：以工業級 CFD 前處理軟體（ICEM CFD / Pointwise / ANSYS Meshing）為參考，
> 修正已查證的問題並逐步補強成熟度。本文件供分階段實作使用，每項可獨立勾選。
>
> 狀態圖例：`[ ]` 未開始　`[~]` 進行中　`[x]` 完成
> 所有發現皆經程式碼核對；誤判項目列於文末「附錄 B」以免重工。

---

## 一、已查證的真實問題（依嚴重度）

| ID | 問題 | 位置 | 嚴重度 | 信心 |
|----|------|------|--------|------|
| R1 | 關閉分頁/關閉程式時不等待或取消背景 worker，lambda 仍持有 session，子程序與暫存檔續跑 | `controllers/session_ctrl.py` (close_tab)、`controllers/backend_ctrl.py`、`controllers/mesh_gen_ctrl.py` | 高 | 已確認 |
| R2 | GUI↔C++ 欄位漂移：C++ 每段讀 `auto_split`/`split_threshold`，GUI 從不寫出（改前端預算分割點）；CLAUDE.md 文件過時 | `models/segment.py` vs `src/main.cpp:515-516` | 中 | 已確認 |
| R3 | 距離式重取樣 `spacing`/`spacing_start`/`spacing_end` 在 GUI 不可達（C++ 已支援） | `models/segment.py` vs `src/main.cpp:583-802` | 中 | 已確認 |
| R4 | 所有匯出 JSON 無 `format_version`，未來格式變動將造成不可回復的資料破壞 | 全部 model、`session_ctrl.py` | 中 | 已確認 |
| R5 | 進度條僅 busy 動畫（`setRange(0,0)`），不顯示百分比、無取消鍵 | `views/main_window.py:382` | 低 | 已確認 |
| R6 | 點擊時 `np.argmin` 對空/None `_active_points` 拋 ValueError（無長度守衛） | `views/canvas.py:805-807` | 中（邊界 crash） | 已確認 |
| R7 | 品質/熱圖模式 `ColorCodedSegmentsItem.paint()` 為 Python 逐段 drawLine + 逐點畫圓、無視窗裁剪，大量點時卡頓 | `views/canvas.py:126-145` | 中（效能） | 已確認 |
| R8 | workspace JSON 以預設 `allow_nan=True` 寫出字面 `NaN`/`Infinity`，C++ nlohmann 重讀可能失敗（非「寫入即崩潰」） | `controllers/session_ctrl.py` (write workspace) | 中（互通） | 已確認 |
| R9 | 座標標籤在滑鼠離開畫布後殘留舊值（無 leave 清除） | `views/canvas.py:826-831` | 低（外觀） | 已確認 |
| R10 | `GeomLoaderThread` 的 `wait()` 在主執行緒可能短暫凍結 UI（race 本身已由 disconnect+wait 處理） | `views/mesh_canvas.py:163-169` | 低 | 已確認 |
| R11 | STL 載入無檔案大小上限 + 純 Python 逐三角形迴圈慢；ASCII 路徑 `errors="replace"` 可能默默損壞座標 | `services/stl_loader.py:58-68` | 低（健全性） | 已確認 |
| R12 | 子程序輸出 stderr 併入 stdout，無日誌分級（INFO/WARN/ERROR），錯誤無法以等級/顏色區分 | `workers/backend_run.py`、`workers/mesh_gen_run.py` | 低（UX） | 已確認 |

---

## 二、分階段 Checklist

### Phase 0 — 穩定性（優先，低風險高回報）✅ 已完成

- [x] **R1 背景執行緒生命週期**
  - [x] 在 `close_tab` 偵測該 session 是否有執行中 worker；若有，取消（`cancel()`+`wait()`）；mesh worker 屬全域不誤殺（`session_ctrl.py:107-117`）
  - [x] worker 完成回呼前先檢查 `session in self.sessions`（不只 `is active_session`）（`backend_ctrl.py` `_on_preview_finished`/`_on_save_finished`）
  - [x] app `closeEvent` 等待/終止所有執行中 worker — 本已存在於 `controller.py:handle_close_event`
  - [x] worker 與 session 綁定追蹤 `self._worker_session`（`backend_ctrl.py:_run_backend`）
  - [x] 驗收：preview 執行中關閉分頁→回呼 early-return 丟棄結果、暫存檔在 `finally` 清除
- [x] **R6 點擊空陣列守衛**
  - [x] `_on_mouse_clicked` guard 加 `or len(self._active_points) == 0`（`canvas.py:783`）
  - [x] 驗收：載入空 session 或切換中點擊→不拋 ValueError
- [x] **R8 NaN-safe workspace JSON**
  - [x] 寫檔前 `np.isfinite` 預掃描，列出含 NaN/Inf 的 session 與欄位並 raise 明確錯誤
  - [x] 改 `json.dumps(..., allow_nan=False)` 先序列化再寫檔（失敗不破壞舊檔）
  - [x] 載入時 `np.isfinite` 驗證，非有限值給警告（`session_ctrl.py:_read_workspace_file`）
  - [x] 驗收：含 NaN 的 session 存檔→明確錯誤；正常存檔→C++ 可重讀
- [x] **R4 schema 版本號（地基）**
  - [x] config 匯出加 `format_version`（`project.py:CONFIG_FORMAT_VERSION=1`）；workspace 加 `format_version`（`session_ctrl.py:WORKSPACE_FORMAT_VERSION=1`）
  - [x] 載入時讀取版本；版本較新給警告、缺欄位視為 legacy(0) 容錯
  - [x] 驗收：舊檔（無版本欄位）仍可載入；C++ 用 `.value/.contains` 忽略未知欄位，無破壞

### Phase 1 — 功能對齊與一致性 ✅ 已完成

> 查證後發現 R3、R12 本已實作；R2 的本質是文件漂移。實際只需動 R2 文件與 R5 進度。

- [x] **R2 auto_split/split_threshold 去留決策** → 採選項 B（GUI 前端預算分割已足夠）
  - [x] 確認 C++ 路徑保留供手寫/CLI config 使用（非死碼），GUI 不發送
  - [x] 更新 CLAUDE.md：修正「segment.py 有 auto_split/split_threshold 屬性」過時敘述，改述 `parameters` 與 `spacing`、並註明 `format_version`
- [x] **R3 距離式重取樣 UI** → 查證後**本已實作**（uniform「By Spacing」）
  - [x] UI 已有 `uniform_type_combo`（By Node Count / By Spacing）+ `uniform_spacing`（`edge_props_panel.py:438-454`）
  - [x] `segment_ctrl._read_params_into_segment` 寫入 `parameters["spacing"]`（:765）；`to_dict` 序列化；C++ `params.contains("spacing")` 走距離式
  - [x] 殘留小缺口**已補**（2026-08-06）：tanh/geometric 的 `spacing_start/end` 現在有 **By End Spacing** 模式。詳見下方「end-spacing 分佈」
- [x] **R5 進度百分比**
  - [x] `MeshGenWorker` 解析 stdout 既有標記（`Step:`、`Boundary Layer progress: a / b`）→ `progress_signal(int)`，單調遞增
  - [x] 進度條改 `setRange(0,100)`+`setValue`（`mesh_gen_ctrl._on_mesh_gen_progress`）
  - [x] 取消鍵本已存在（`cancel_mesh_btn`/`mesh_cancel_btn` → `cancel_mesh_generator`）
- [x] **R12 stderr 分離 + 日誌分級** → 查證後**本已實作**
  - [x] `log_panel.log` 已依內容/ANSI 自動分級並上色（INFO 灰 / WARN 橙 / ERROR 紅）
  - [x] 決策：維持 `stderr=STDOUT` 合流 + 內容分級（避免雙管線死鎖風險；分級實效已達成）

### Phase 2 — 效能與健全性 ✅ 已完成

- [x] **R7 大資料集渲染**
  - [x] `ColorCodedSegmentsItem.paint` 改用 `QPainterPath`，依顏色批次連續線段，減少 setPen/draw 次數
  - [x] 視窗裁剪：以 `option.exposedRect`（含 margin）剔除畫面外線段與符號（`canvas.py`）
  - [ ] 驗收實測 frame time（**待實機**：需 50K 點資料於有顯示環境量測）
- [x] **R9 座標標籤離開清除**：`_throttled_mouse_update` 在 `contains(pos)` 為 false 時清空 `coord_label`
- [x] **R10 GeomLoaderThread 非阻塞**：改世代 token（`_geom_loader_gen`），舊結果以 token 比對丟棄；不再主執行緒 `wait()`；保留 thread 參照避免 GC；close 時等待全部
- [x] **R11 STL 健全性**
  - [x] 載入前檔案大小上限 `MAX_STL_BYTES=256MB`，超過給明確錯誤
  - [x] 二進位解析向量化（`np.frombuffer` + 結構化 dtype，取代逐三角形迴圈）
  - [x] ASCII 嚴格解碼（`utf-8` strict），失敗報錯而非 `errors="replace"`

### Phase 3 — 工業級成熟度

- [x] **自動存檔 / 崩潰復原**：`controller.py` 每 60s checkpoint 已修改的 session 至穩定路徑 `tempfile.gettempdir()/hybmesh_preprocessor_autosave.hws`；啟動偵測殘留檔→提示復原；乾淨關閉刪除檔並停止 timer；背景寫檔失敗（如暫態 NaN）靜默略過
- [x] **格式遷移工具**（地基）：`format_version` 已落地，載入端對缺欄位視為 legacy(0) 容錯、較新版本給警告。v0→v1 為加欄位相容，無需破壞性遷移；待真正不相容變更時再加 migrate 函式
- [ ] **單位系統**（**未做 — 大型跨元件，建議獨立進行**）：需 config/JSON 加 `"unit"`、GUI 載入轉換、且 **C++ 端對應**；牽涉求解器數值，風險高，不宜與本批一起倉促導入
- [x] **幾何統計面板**（2026-08-06）：CAD sidebar 新增「Geometry Statistics」摺疊區（預設收起 —— sidebar 固定 360px，edge properties 優先）
  - `services/geometry_stats.py`（Qt-free）：點數/段數/開閉/bbox/範圍/周長/間距 min-mean-max/**均勻度**
  - **最有價值的是均勻度**：相鄰間距的最大擴張比。超過 1.2× 會讓 BL 長得很差，而在此之前只能「產生網格看它爆掉」才發現。門檻與 `.dat` quality heatmap 一致，兩者不會互相矛盾
  - 擴張比**方向無關**（2× 驟縮與 2× 驟增同樣糟），並回報最差處**位於哪個點**，讓數字可行動而非只是判決
  - **閉合幾何把接縫段納入**周長與比值統計 —— 那是真實的網格邊，而最差的跳變常常正好在接縫
  - 退化輸入（空/單點/全 NaN/全重複）回 `{}` 而非捏造 0，UI 顯示「—」；非有限點被丟棄而非傳播
  - 只有均勻度那一列會變色（那是唯一帶「判斷」而非「量測」的數字）；清空 sidebar 時歸零，不留上一個幾何的數字
  - `tests/test_geometry_stats.py`（26 checks）；全套 **35/35**
  - **需你實機確認**：摺疊區的位置與字級（我只能驗證數值與變色邏輯，不能驗證好不好看）
- [ ] **畫布工業工具**（**未做 — 大型互動 UI**）：量測/座標輸入/grid snap/視角歷史，需大量互動測試，不宜在無顯示環境盲改
- [x] **檔案完整性 hash**（2026-08-06）：workspace 每個 session 記錄 `source_fingerprint`（size + mtime + SHA-256），載入時比對並回報
  - 問題本質：workspace 存的是幾何**點陣列**＋來源路徑，兩者脫節時沒人發現。若 `.dat`/`.stl` 在存檔後被重新匯出/腳本重生/手改，重開時 canvas 顯示**存檔時的點**、而 mesh 階段**重讀磁碟上的新檔** → 網格是使用者沒看過的幾何
  - 刻意只**回報**不阻止：磁碟上的檔案可能才是新的事實，由使用者決定
  - 成本：256MB STL 雜湊約 1 秒，而 autosave 每 60 秒跑一次 → `fingerprint()` 接受前次記錄，size+mtime 未變就重用 digest（實測確認不重算）
  - 分級：`ok` / `changed` / `missing` / `unverified`（無記錄或版本較新 → unverified，**絕不誤判為 mismatch**）
  - 已知界限並誠實記錄在測試中：size+mtime 都被偽造成相同時，快路徑會判 ok；任何真實編輯都會改變其中之一
  - `tests/test_file_integrity.py`（19 checks）；全套 **34/34**
- [ ] **批次處理**（**未做 — 大型功能**）：job queue 多幾何批次跑 mesh + 整體進度

> **Phase 3 範圍說明**：自動存檔/復原（資料安全、與 Phase 0 同主題）與格式遷移地基已完成。其餘為大型 UI／跨元件（含 C++）功能，且在無顯示環境下無法互動驗證——為避免將未經實機測試的功能倉促併入，標記為待獨立進行，並附上理由。

---

---

## 四、第二輪複查（2026-08-06）— 前一輪未涵蓋的問題

> 前提：R1–R12 皆已落地、headless 迴歸 22/22 綠。本輪針對**上表未涵蓋**的面向重查，
> 依 ICEM CFD / Pointwise / Fluent 的專案檔、行程管理、部署可攜性標準。

| ID | 問題 | 位置 | 嚴重度 | 狀態 |
|----|------|------|--------|------|
| N1 | Save Workspace 不含 Mesh/Solver/IB 設定 → 案例不可復現；autosave 也只看幾何 | `session_io_ctrl.py`、`lifecycle_ctrl.py:50` | **高** | [x] 已修 |
| N2 | 兩個都不完整的「專案檔」格式並存（`.hws` 無 mesh/solver；pipeline JSON 單一 CAD + 無 IB 段） | `session_io_ctrl.py` vs `pipeline_config.py` | **高** | [x] 已修 |
| N3 | GUI/headless 執行 mesher 未注入 gmsh 動態庫路徑 → 換機器即 dyld 失敗 | `mesh_gen_run.py`、`backend_run.py`、`pipeline_runner._mesh_env` | **高** | [x] 已修 |
| N4 | 小數位/下限硬編（BL 初厚下限 1e-6、`setDecimals(4)`），且不接受科學記號 → 高 Re 案例做不出來 | `mesh_config_build_mixin.py:151`、`clean_double_spin_box.py` | 中 | [x] 已修 |
| N5 | `cancel()` 只 SIGTERM 不升級、關閉時 `wait()` 無 timeout、子孫行程不被清 → 可能凍結不掉 | `*_run.py`、`lifecycle_ctrl.py` | 中 | [x] 已修 |
| N6 | Undo 僅覆蓋 CAD 幾何；Mesh/Solver/BC/IB 編輯不可回復，且 stack 隨分頁切換 | `commands/base.py`、`controller.py:336` | 中 | [x] 已修 |
| N7 | **36** 處 `except Exception: pass` 靜默吞例外（已有 rotating log 卻沒用；先前報 52 是 grep 把非 `Exception` 的處理器也算進去） | `canvas_draw_mixin.py` 等 | 中 | [x] 已修 |
| N8 | 105 處 `blockSignals` + 20 處 `_is_populating` → 無單一資料流方向 | 全 views/controllers | 中 | [~] 護欄部分已修；架構重構未做 |
| N9 | 零 i18n（`tr()` grep = 0），全字串硬編英文 | 全 GUI | 低 | [ ] 未做 |
| N10 | 沒有 status bar（模式/座標/選取數/單位/背景進度無常駐顯示） | `main_window.py` | 低 | [x] 已修 |
| N11 | 視窗版面不持久化（`QSettings` 只用於 recent files） | `session_load_ctrl.py:239` | 低 | [x] 已修 |
| N12 | 錯誤嚴重度未分級 —— **原判斷前提有誤**（只數了靜態 `QMessageBox.critical()`，漏掉已用 `Icon.Critical` 的 `report_error()`）；真實缺口是匯出失敗誤報為 warning + 多處 modal 無 headless guard | 全 controllers | 低 | [x] 已修 |
| N13 | 22 測試檔 / 173 模組；CI 未跑 lint、未 build C++（介面漂移無守門） | `tests/run_all.sh`、`.github/workflows/gui-tests.yml` | 低 | [x] 已修 |

### 已完成：N3 → N5 → N1（2026-08-06）

- [x] **N3 gmsh loader path 注入**
  - [x] 新增 `services/env_setup.py`：`gmsh_lib_dir()`（`HYBMESH_GMSH_LIB_DIR` 覆寫 → gmsh 模組探測，含 pip/conda/homebrew 佈局）、`mesher_env()`、`gmsh_missing_hint()`
  - [x] `mesh_gen_run` / `backend_run` 的 Popen 加 `env=mesher_env()`；`pipeline_runner._mesh_env()` 改為自行解析；resample stage 也帶上
  - [x] **根因**：macOS SIP 會在受保護的 `python3` 啟動時清除所有 `DYLD_*`，所以「靠 shell wrapper 匯出」在 Python 下方**永遠不可能生效**——先前能跑純粹靠 binary 內寫死的 LC_RPATH（實測 `DYLD_LIBRARY_PATH=/tmp/probe python3 -c ...` → `None`）
  - [x] 移除 `run.sh` / `run_pipeline.sh` 的開發機硬編 fallback，抽成共用 `tools/scripts/gmsh_lib_dir.sh`（找不到→警示，不再假裝有路徑）
  - [x] **驗收（實測）**：把 binary 副本的 LC_RPATH 完全剝除後，無注入 → `rc=-6` + `Library not loaded: @rpath/libgmsh.4.15.dylib`；經 `MeshGenWorker` 注入後 → `rc=0`、正常進入 C++
- [x] **N5 行程終止升級 + 有界關閉**
  - [x] 新增 `workers/proc_util.py`：`popen_kwargs()`（`start_new_session=True`）、`stop_process()`（SIGTERM→grace→SIGKILL，對 process group）、`stop_process_async()`（0 ms 返回，升級交給 daemon thread，Cancel 鍵不卡 UI）、`kill_process()`
  - [x] 四個 worker（mesh/backend/solver/stl3d）的 `cancel()`、cancel 分支、timeout 分支全部改走 helper；solver 的 `mpirun -np N` 各 rank 現在也會被清掉
  - [x] `lifecycle_ctrl` 重寫為 `_shutdown_workers()`：每個 worker 有界 join（`_JOIN_MS=4000` → kill child → `_JOIN_AFTER_KILL_MS=2000`），逾時者記入 module-level `_abandoned_workers` 保住參照（避免 "QThread destroyed while running"）而**不阻塞退出**；順帶把先前漏掉的 `_solver_worker` 納入
  - [x] **驗收（實測）**：對「忽略 SIGTERM 且 fork 子孫」的行程，裸 `terminate()` → 父與子孫全部存活；`stop_process` → 1.0s 內全清；`stop_process_async` → 0 ms 返回且仍成功清除
- [x] **N1 完整專案狀態持久化 + project-level dirty**
  - [x] `WORKSPACE_FORMAT_VERSION` 1 → 2，新增 top-level `project` 區段（`mesh_config` / `solver_config` / `stl3d_config` / `vtk_path` / `result_path`）
  - [x] 新增 `controllers/project_state_ctrl.py`（`ProjectStateControllerMixin`）：`_collect_project_state()` 從**面板**讀取（不是從只在執行階段才更新的 `global_*`）、`_apply_project_state()`、`_reset_project_baseline()`、`project_is_dirty()`
  - [x] dirty 判定採**基準快照比對**而非 signal：solver 面板沒有 `config_changed`，且 `valueChanged` 會被 `set_config()` 的程式化賦值觸發（signal 版會誤報）；基準在 load 後由面板重新採樣，避免 spinbox 夾值造成「永久 dirty」
  - [x] autosave 觸發條件改為 幾何變更 **OR** `project_is_dirty()`；關閉提示分項列出「幾何 sessions」與「Mesh/Solver/IB 設定」
  - [x] v1→v2 migration 補空 `project` 區段，舊 workspace 照舊可載入
  - [x] `_read_workspace_file` 的「將關閉所有分頁」modal 加 offscreen guard（比照 `_maybe_recover_autosave`），headless 不再卡死
  - [x] `session_io_ctrl.py` 拆檔後 435 行，符合 ~500 行上限
- [x] **迴歸測試**：`tests/test_gui_review_batch_2026_08_06.py`（33 checks，涵蓋 N3/N5/N1 含「裸 SIGTERM 不夠」的反向對照）；全套 **23/23 PASS**；`./run.sh` 與 `./run_pipeline.sh --no-solver` 端到端實跑通過（5520 far-field 三角形）

### 已完成：N4 → N7（2026-08-06，同日第二批）

- [x] **N4 科學記號數值輸入**
  - [x] 新增 `views/clean_double_spin_box.py::SciDoubleSpinBox`（繼承 `NarrowDoubleSpinBox`）：覆寫 `textFromValue`（`%.6g`）、`valueFromText`、`validate`、`fixup`、`stepBy`
    - 輸入接受 `1.2e-7` / `3E+3`，並容忍 locale 的小數逗號；顯示一律用 `.`，與 `.dat`/JSON 的 C-locale `%.6g` 一致
    - `validate` 對「還在打字」的前綴（`""` / `-` / `1e` / `1e-` / `.`）回 Intermediate，不會打到一半被擋掉；超出範圍也回 Intermediate 並由 `fixup()` 夾值
    - `stepBy` 每次重算「比自身量級低一個十的次方」的步長（1e-6 → 步 1e-7），取代 Qt 的 1.0
    - `setKeyboardTracking(False)`：`1e-7` 的每個前綴（`1`、`1e`）本身都是合法數字，逐鍵 `valueChanged` 會短暫把 `1` 當成網格尺寸套用並觸發預覽/dirty 連鎖；改為 Enter / 失焦才提交
    - 支援 `specialValueText`（`seed_size`/`seed_radius` 的 "auto"）——Qt 原本在自己的 validate/interpret 裡處理，被覆寫後必須自己補
  - [x] 轉換受影響欄位（下限一律放寬到 0，由 `MeshConfig.validate()` 給語意錯誤而非 UI 靜默夾值）：
    `bl_initial_thickness`（原 `setRange(1e-6, 1.0)`+`dec 6`）、`surface_mesh_size` / `farfield_mesh_size`（原 `1e-4` 下限）、
    `domain_x/y_min/max`（原 `dec 4`）、`seed_size` / `seed_radius`、CAD `uniform_spacing` 與 `shape_dialog._spacing_spin`、
    per-geometry BL dialog 的 `BL_INITIAL_THICKNESS`（`_BL_FIELD_SPECS` 加 `sci=True`）
  - [x] `apply_smart_spin_steps` 跳過 `SciDoubleSpinBox`（它的固定步長是啟動時算一次的，跟不上會跨數個量級的值）
  - [x] 建構時明確 seed `MeshConfig` 預設值——舊欄位是靠 `minimum=1e-6` 隱式夾上去的，現在 0 合法，未 populate 的面板否則會讀到 0
  - [x] **驗收（實測）**：面板輸入 `2.5e-7` → `get_config()` → `.dat` 寫成 `BL_INITIAL_THICKNESS 2.5e-07` → 重載無損 → C++ `ss >> double` 正確解析（無 `<=0` 警告，BL 58/58 生成、150373 far-field 三角形）
- [x] **N7 靜默例外全面改為記錄**
  - [x] `services/logging_setup.py` 新增 `get_logger(__name__)`（`hybmesh.gui.<module>` 子 logger，`configure_logging` 之前即可使用）
  - [x] formatter 加 `%(name)s`，訊息可追回發生模組；新增 `HYBMESH_LOG_LEVEL` 環境變數（預設 INFO，設 DEBUG 才輸出 best-effort 診斷，平時不製造雜訊）
  - [x] 34 處改為分級記錄（皆 `exc_info=True`，保留完整 traceback）：
    - **22 處 `debug`** — 真正的 best-effort：游標設定/還原、`disableAutoRange`、`viewRange`、`removeItem` 拆除、colorbar 移除、3D grid 顏色/相機、temp dir 清除、關閉時的面板記錄
    - **12 處 `warning`** — 會靜默降級使用者要求的行為：snap callback 失敗（點沒吸附）、weld handle 收集失敗、iso-line 繪製失敗、probe overlay 遺失、pipeline script 與畫面不一致、匯出讀不到即時檔名、`worker.cancel()` 拋錯
  - [x] 其中兩處使用者影響最大的（pipeline script 與畫面不符、匯出用錯檔名）**同時**寫到 log panel，不只寫檔
  - [x] 剩餘 4 處刻意保持 `pass` 並在原地註明理由：`log_panel`（這就是寫檔路徑，記錄會遞迴）、`logging_setup` ×2（setup 與 excepthook）、`proc_util._escalate`（終端 catch）
  - [x] **驗收**：`test_silent_exceptions.py` 靜態掃描鎖住「不得再出現未註明的 `except Exception: pass`」，並實際觸發 warning/debug 兩條路徑確認 traceback 進入 gui.log
- [x] **全套迴歸 25/25 PASS**；`./run_pipeline.sh --no-solver` 端到端通過；所有改動檔案仍在 500 行以內

### 已完成：N2（2026-08-06，同日第三批）

- [x] **N2 一個檔案完整描述一個 case**
  - [x] `PIPELINE_FORMAT_VERSION` 1 → 2：`cad`（單一物件）改為 **`cads` 陣列**，新增 **`stl3d`（IB）段**
    - **具體資料遺失**：`save_pipeline_file` 只取 `active_session()`，其他開著的 CAD 分頁**全被靜默丟棄**且無法從 script 還原（多元件翼、物體＋地面板等多體案例根本無法用 script 描述）
    - `cad` 保留為 **property**（指向 `cads[0]`，含 setter），v1/v0 script 與手寫單幾何 script 全部照舊可讀；v1→v2 migration 把 `cad` 折進 `cads`
    - 每筆各自獨立：`cad_skip(i)` / `resolve_input_file(repo, i)` / `default_cad_output(repo, i)` / `build_project_model(repo, out, i)`；預設輸出檔名以來源 stem 命名，多幾何不會互相覆蓋
  - [x] `build_mesh_config` 接受路徑**列表**，全部依序去重後成為 mesh 邊界（mesher 用路徑為 key 綁 role/BL override，順序即案例定義）；mesh 檔名取 `geom_files[0]`（主體）
  - [x] headless runner 逐筆 resample（`cads_all_skipped()` 判斷是否整段跳過），回傳新增 `cad_outs` 清單、`cad_out` 保留相容；有 `stl3d` 段時**明講** headless 不執行 IB（不靜默略過）
  - [x] GUI：Save 寫出**全部** session（**分頁順序**，比 active-first 可預測且可重現）＋ `stl3d`；Load 每筆開一個分頁並套用 IB 段；Run All 依序 resample 每個有幾何的 session（`_pipe_cad_queue`），abort 時清空佇列
  - [x] `.hws` ⇄ script 互轉：`PipelineConfig.from_workspace_dict()`＋`_looks_like_workspace()`（依**內容**判斷，非副檔名），`run_pipeline.sh` 因此可直接吃 `.hws`；machine-specific solver 路徑照舊剝除以保可攜，view-only 狀態（快取重取樣點、選取、active tab）刻意丟棄
  - [x] 新增 `config/pipeline/multi_element_demo.json`（JAXA 30P30N slat＋flap 兩體）
  - [x] **驗收（實測）**：兩體案例端到端跑通（20621 far-field 三角形、966 boundary edges、兩體都長了 BL）；v1 的 `naca_demo.json` 不受影響仍正常
  - [ ] **未做（明確記錄）**：headless **不執行 IB 階段** —— staging 邏輯目前綁在 Qt 的 `stl3d_ctrl.run_stl3d` 裡，需要先抽出 `services/stl3d_case.py`（比照 `solver_case.py`）才能無 GUI 執行；格式與 GUI 已完整支援
  - [ ] **未做**：完整三元件構型（加入主翼）需針對 slat 縫道（約 1% 弦長）與主翼 flap cove 調 BL 尺寸，否則 offset front 自撞 —— 屬 BL/幾何尺寸問題，非 multi-geometry pipeline 的限制（已註明在範例檔內）

### 已完成：N6（2026-08-06，同日第四批）

- [x] **N6 全域 undo（跨分頁 + 涵蓋 Mesh/Solver/IB）**
  - [x] **序號排序而非合併 stack**：`commands/base.py` 加全域單調 `next_seq()`，`CommandHistory._push` 為每個 command 蓋章，新增 `peek_undo_seq()` / `peek_redo_seq()`
    - 為什麼不把歷史合成單一 stack：per-session history 才能讓「關閉分頁 = 剛好丟掉該分頁的 command」；合併後關閉分頁會在歷史中留下指向已死 session 的洞
    - undo 取**所有 stack 中 seq 最大**者；redo 取**所有 redo stack 頂端中 seq 最小**者（undo 既然總是取最大，最後被 undo 的就是 seq 最小的那個 → 完全鏡像）
  - [x] **新增 `controllers/undo_ctrl.py`（`UndoControllerMixin`）**，`controller.py` 的 undo/redo 全部移出（352 行）
    - undo 命中其他分頁的 command 時，**先把該分頁帶到前景**再套用 —— 復原看不見的東西比不復原更糟
    - `_update_undo_redo_buttons` 改為檢查**所有** history（原本只看 active session）
  - [x] **`commands/config_cmds.py::UpdateProjectStateCmd`**：快照式（比照 `UpdateSegmentStateCmd`），before/after 深拷貝（`geom_roles`/`group_bc`/`bc_definitions` 都是嵌套容器，淺拷貝會被後續編輯改到）
  - [x] **去抖動快照 diff recorder**（600 ms）：一串連續輸入合成**一個** undo step（「復原我上一個改動」，不是「復原一個數字」）；diff 為基礎，所以被誤觸發也零成本
    - `before` 在 **burst 開始時**才取（來自上次 commit 的參考點），不是啟動時固定 —— 否則任何程式化 `set_config` 都會讓它過時，undo 會跳回使用者從未見過的 widget 預設值（實測發現並修正）
    - 三個面板**一律用通用 widget 接線**：`mesh_config_changed` 不會為 scalar 編輯發射、solver 面板根本沒有 change signal，只靠面板 signal 會讓 domain box、迭代數這類編輯靜默逃出 undo
  - [x] **`push_panel_config(panel, cfg)` 單一漏斗**：17 個程式化推送站點全部改走它（`suppress_project_undo()` 抑制錄製）。只有 IB 面板自己 block signals，另兩個會漏 —— 未經抑制的話「進入 Mesh 階段」「載入檔案」都會被當成使用者輸入記進 undo。走單一 helper 而非 17 個手寫 `with`：未來漏掉只會多錄一步，不會弄壞基準
  - [x] `undo()`/`redo()` 先 `flush_project_snapshot()`：剛打完字就按 Ctrl+Z 不會跳過那筆編輯
  - [x] 排除 artefact 路徑（`vtk_path`/`result_path`）：那是執行階段的**輸出**，「復原一次網格生成」不是一件事
  - [x] 順手修：`close_tab` 的未存檔 modal 沒有 offscreen guard（headless 永久阻塞）；`is_headless()` 抽到 `app/utils.py` 供三處共用
  - [x] **驗收**：`test_global_undo.py`（39 checks）—— 含跨分頁時序、分頁前景切換、redo 鏡像、關閉分頁後其餘歷史仍可用、burst 合成、pending 編輯 flush、undo 不自我重錄。全套 **27/27 PASS**

### 部分完成：N8 護欄安全（2026-08-06，同日第五批）

> 範圍決定：N8 原本的描述（「收斂為單一資料流」）是**架構重構**，涉及重寫 panel↔model
> 同步，風險過高。本批只做其中**可客觀量測、可靜態鎖住的 bug class**，架構部分明確留待獨立進行。

- [x] **43 處未保護的 `blockSignals(True) … (False)` 全部改用 `block_signals()` context manager**
  - 真正的風險：兩半之間若拋例外，unblock 那行**永遠不會執行**，widget 從此**永久無法發射訊號** —— 靜默失效、也沒有 traceback 可查
  - 先量測：46 處未保護（其中 `bc_widget` 與 `shape_dialog` 兩處本來就有 `try`，是我的匹配器沒認出）
  - 也查了「body 內有 `return`/`continue` → 必然洩漏」的更嚴重情況：**沒有**（`mesh_layers_ctrl:153` 的 `continue` 在 block 內的 `for` 迴圈裡，不會離開函式）
  - 41 處由腳本轉換（帶縮排一致性驗證，不確定的跳過），5 處手動處理：`transform_ctrl` 的 `for w in pivot_fields` 迴圈式 block、`shape_spec` 的條件式 `if silent:`（改用 `nullcontext()`）、以及兩處分號並列寫法
  - `shape_spec` 的條件式改寫也順手消掉了那個模式：`block_signals(w) if silent else nullcontext()`
  - 現在 `with block_signals(...)` 共 48 處，未保護 **0** 處
- [x] **`_is_populating` 由裸 bool 改為深度計數 + `populating()` context manager**
  - 誠實記錄：四個設定點**本來就有 try/finally**，所以「洩漏」的擔憂在這裡**不成立** —— 我沒有去修沒壞的東西
  - 真正的問題是 bool **無法嵌套**：內層 populate 離開時會在外層還在寫 widget 時就把旗標清掉，讓其餘的程式化寫入被當成使用者輸入
  - `_is_populating` 改為唯讀 property（讀 `_populating_depth > 0`），寫入只能透過 `controller.populating()`
  - `segment_ctrl` 原本 `finally` 裡還有一行 canvas 清理，轉換後保留在 `try/finally` 中 —— 例外路徑仍會清掉殘留的 duplicate preview（未因重構而丟掉）
- [x] **驗收**：`test_signal_guards.py`（18 checks）—— **靜態**鎖住「不得再出現未保護的 `blockSignals`」與「不得直接賦值 `_is_populating`」，加上 context manager 的例外安全/嵌套行為，以及「選取邊（重度 populate）不會回寫模型、不產生 undo step」的功能驗證。全套 **28/28 PASS**，lint 未變差（兩檔還變好）
- [ ] **未做（架構部分）**：把 panel↔model 同步收斂成單一 `apply_panel_to_config()` / `apply_config_to_panel()` 對，建立單一資料流方向。N6 的 `push_panel_config()` 已經是「單一寫入口」的雛形，可作為起點。這是獨立的重構專案，需要逐面板進行並有互動驗證。

### 已完成：N11 + N12（2026-08-06，同日第六批）

- [x] **N11 視窗版面持久化**
  - [x] 新增 `services/ui_state.py`：`save_ui_state()` / `restore_ui_state()` / `restore_active_stage()`
    - 存：視窗 geometry、dock state（`saveState()`）、目前 stage、每個 collapsible section 的展開狀態
    - **不存**任何案例資料 —— 還原版面絕不能改變「會被 mesh / solve 的東西」
  - [x] **以 `LAYOUT_VERSION` 命名空間**：版面日後不相容變更時 bump，舊狀態會被**忽略**而非還原進一個已不符的視窗（還原成錯的比預設的更糟，而使用者很難自己重設）
  - [x] **headless 完全不讀不寫** QSettings —— 否則測試與批次執行會用 offscreen 的版面覆蓋掉真實使用者存的版面
  - [x] section key = 所屬 sidebar 頁的 class name + section title（同名 section 各自獨立，不共用旗標）；`CollapsibleSection` 補上 `title` 屬性作為穩定 key
  - [x] **實測抓到真缺陷**：Qt 警告 `objectName not set for QDockWidget 'Log Console'` —— **沒有 objectName 的 dock 會被 `restoreState()` 跳過**，dock 持久化本來是靜默無效的。補上 `setObjectName("logConsoleDock")` 後警告消失、狀態才真的存得回來
  - [x] stage 的還原刻意與版面分開、最後執行：切換 stage 會觸發面板 populate，需要 controller 已完全接線
- [x] **N12 訊息分級與 headless 安全**
  - [x] **先更正原判斷**：我當初只數了靜態方法 `QMessageBox.critical()`，漏掉 `report_error()` 早已使用 `Icon.Critical`，而且專案已有清楚的 error/warning 語意（寫入失敗 vs 讀取失敗）。**「完全沒有分級」的說法是錯的**
  - [x] 真實缺口一：**STL 匯出失敗（寫入失敗）卻報成 warning**，違反專案自己的慣例 → 改為 `report_error`
  - [x] 真實缺口二：前置條件提示（「先畫一個閉合輪廓」）warning/information 混用 —— 什麼都沒壞卻用失敗的等級呈現，會訓練使用者忽略真正的問題 → 新增 `report_info()`
  - [x] 真實缺口三：**多處手寫 `QMessageBox` 沒有 headless guard**，在測試/CI/headless pipeline 就是掛住。先前已逐點補過三次（autosave 復原、load workspace、close tab）—— 這次把 guard 收進 helper：新增 `confirm(..., headless_default=)`，13 處 prompt 全部改走 helper（含關閉程式的未存檔提示，先前**也沒有** guard）
  - [x] `headless_default` 依語意設定：「還是要繼續嗎」→ True（批次要能往下走）；「要不要順便跳到下一階段/開始跑網格」→ False（批次不該被靜默帶去別的地方）；autosave 復原 → False（offscreen 執行不該繼承別人的 autosave）
  - [x] 順手清掉 6 處因此變成未使用的 `QMessageBox` import（未動既有的 F401）
- [x] **驗收**：`test_ui_state_and_dialogs.py`（24 checks）—— 版面 round-trip、版本 bump 忽略舊狀態、**headless 一次也不碰 QSettings**、section key 唯一性、三種嚴重度對應正確的 icon、`confirm()` 回傳 default 而非阻塞、**靜態**檢查不得再出現 helper 之外的裸 `QMessageBox` 嚴重度/問句呼叫。全套 **29/29 PASS**

### 已完成：N13（2026-08-06，同日第七批）

- [x] **N13 CI 三道 gate**
  - [x] **lint gate**：新增 `tools/PreProcessor/gui/ruff.toml`
    - 全規則會報 ~520 個問題（其中約 180 個是專案刻意使用的分號/長行風格）—— **永遠紅的 gate 等於沒有 gate**，所以 enforced set 只選會抓到**真實缺陷**的規則（`E9` 語法、`F` pyflakes），並在檔內逐條寫明為什麼不啟用 E501/E7xx/E741
    - 修掉 enforced set 下的 **331** 個違規：5 個真實發現（3 個未使用區域變數、1 個重複 import、1 個遮蔽變數）手動處理，326 個未使用 import 由 ruff 自動修
    - **自動修改破壞了一個 re-export，被完整測試套件抓到**：`dll_templates.py` 是純門面模組卻沒有 `__all__`，ruff 把 `render_phi_field_init` 等當成未使用而移除，21 個測試立刻在 import 時失敗。修法是加上 `__all__` 明確宣告門面角色（比逐行 `# noqa` 更能永久防護），並移除經查證確實沒人使用的 2 個死 re-export
    - 測試目錄的 4 個發現中，`app = QApplication(...)` 是**必須保留參照**的（否則 QApplication 會被回收），用 `# noqa: F841` 加理由而非刪除
  - [x] **C++ build gate（`-Werror`）**：CMakeLists 的註解本來就寫著「`-Werror` 屬於 CI」。先量測只有 **4 個 warning**，全部修好後 `-Werror` 乾淨通過：
    - `Mesh::addEdge` 的 `{v1, v2}` 漏了 `bcTag`/`segKey` 初始化 → 改為明確建構並註明那兩個欄位刻意用 in-class 預設
    - `Spacing.hpp::generateCurvature` 的 `L`/`min_ds`/`max_ds` 是共用 signature 的一部分但此策略不需要 → `[[maybe_unused]]`（不改 API、不改行為）
  - [x] **test gate 改為 build 之後執行**：先前 CI 不 build C++，所以**需要 binary 的測試全部自我跳過** —— GUI↔C++ 介面壞掉 CI 也是綠的。現在 `test` job `needs: build`，下載 artifact 後執行，並加跑 `./run_pipeline.sh --no-solver` 端到端（GUI 的 config writer 真的餵給 mesher，不是 mock）
  - [x] **真正的漂移守門**：新增 `tests/test_gui_cpp_config_parity.py` —— 靜態比對 GUI writer（`mesh_config_io.py`）寫出的 key 與 C++ reader（`Config.hpp`）解析的 key。**GUI 寫出但 C++ 不解析 = 使用者設了值、GUI 存了、mesher 靜默忽略、網格不是要求的那個，而且哪裡都沒有錯誤** —— 這正是第一輪 R2 那類問題。不需要 binary，可守每一次 push
    - 這個 gate 一啟用就抓到 5 個 C++-only key，**逐一查證**後確認全部合法並寫入 `KNOWN_CPP_ONLY` 附理由：`SEED_SIZE`/`SEED_RADIUS`/`SEED_MODE` 是手寫 config 的全域 fallback（GUI 實際把 per-seed 值寫成 `SEED_FILE` 行上的 positional token，已核對 C++ 解析端）、`GMSH_NUM_THREADS` 無 GUI 控制項、`BL_FRONT_SMOOTHING_ITERS` 是刻意不暴露的診斷開關。新出現的 C++-only key 會讓測試失敗，強迫同等審視
  - [x] **驗收**：三道 gate 本地全部跑過（lint 全綠、`-Werror` build 乾淨、30/30 測試 + e2e 網格 5520 三角形）

### 已完成：headless IB 階段（2026-08-06，同日第八批）— 補完 N2 留下的缺口

- [x] **抽出 `services/stl3d_case.py`（Qt-free）**：比照 `solver_case.py`，把 staging 從 Qt 綁定的 `stl3d_ctrl.run_stl3d` 分離
  - `validate()`（前置條件，GUI 與 headless 共用同一套拒絕理由）、`work_dir_for()`、`prepare_case_dir()`（回傳 work_dir / para_path / phi_path / binary / threads）、`omp_threads()`、`describe()`
  - GUI controller 改為呼叫它（不再自留一份 staging 邏輯），格式知識仍留在 `Stl3dConfig`
- [x] **headless runner 新增真正的 IB 階段**：`_run_stl3d()` 走 `stdin=para.in`（就是 binary 的互動答案），跑在 mesh 之前（solver 階段要 link 它產出的 phi）；`run_pipeline(run_ib=)` ＋ CLI `--no-ib`，與 `--no-solver` 對稱；`out["phi"]` 納入 artifact 回報
- [x] **實測時發現並修掉一個既有的真實 bug（GUI 也同樣受害）**：
  - `Stl3dConfig.para_in_text()` 寫 **6 行**，第 2 行是 ASCII/binary 的 `y/n` 答案 —— 但 `stl3d.cpp` **已改為自動偵測**格式而不再詢問（C++ 註解明寫），只剩 **5 次 `cin >>`**
  - 於是那多出的一行被讀成 **case name**：真正的 case name 被當成 domain 讀取 → `cin` 在非數值 token 上失敗 → **產出空的 phi 場、檔名還是錯的（`y_phi_tec.dat`），而 exit code 是 0**
  - GUI 用同一個 writer，所以 GUI 的 IB 階段**一樣是壞的**。修法：移除那一行（`ascii` 欄位保留為面板顯示用），並在 docstring 寫明必須與 `stl3d.cpp` 的 5 次讀取逐行對應
  - 我自己也曾在 `validate()` 多加一條「Z 範圍必須 max > min」—— 但這是 2D 專案，STL 是 z=0 平板，`zmin == zmax` 是正常情況，該檢查會拒絕**所有**正常案例。已改為只拒絕反向範圍（`zmax < zmin`）
- [x] **同類的靜態守門**：新增 `tests/test_stl3d_case_parity.py` —— 直接從 `stl3d.cpp` 解析 `cin >>` 序列，逐行比對 `para.in` 的行數與每行 token 數。這個 bug 的本質就是 Python writer ↔ C++ reader 漂移，與 `test_gui_cpp_config_parity.py` 同一類，所以用同一種方式鎖住
- [x] **驗收（實測）**：naca0012.stl → 30x24x1 網格 → phi 場 720 點、其中 202 點標記為固體（翼型內部，物理上合理）；`para.in` 5 行與 binary 對齊；全套 **31/31 PASS**

### 已完成：end-spacing 分佈（2026-08-06，第十批）— 補完 Phase 1 殘留

牆面第一格尺寸原本只能靠猜一個抽象的 intensity / growth ratio 逼近。tanh 與
geometric 現在都有 **By End Spacing** 模式。過程中修正兩件事：

- [x] **tanh 的 spacing 支援其實是壞的**：`main.cpp` 用啟發式 `log(L/min(s0,s1))*0.5`
  把要求映射成 clustering 參數 —— **實測差約 40 倍**（要求 1e-4 實得 2.5e-6），
  而且**要求兩端都給**，單邊請求會靜默退回 `intensity`。改為
  `Spacing::solveTanhDelta()`（bisection 真求解，`generateTanh` 的第一段對 dlt 單調遞減，
  所以二分法安全；比 uniform 還粗的請求回 0 → 退化為 uniform 而非夾到誤導值）
- [x] **tanh 本質對稱，我原先的 UI 設計錯了**：先做成兩個獨立欄位（Δs start / Δs end），
  但 tanh 物理上不可能兩端不同 —— 那是**分佈做不到的承諾**。改為單一「Δs at ends」欄位；
  只有 geometric（真的非對稱、且本來就是真求解）保留 start/end 兩個欄位
- [x] 兩個模式**互斥寫入**：選了 spacing 就不寫 intensity/ratio（一個量兩個來源就是漂移的起點）；
  未設定的端點（顯示 "unset"）**省略而非寫成 0.0**，那是 resampler 區分單邊/雙邊的依據
- [x] 模式由 **key 是否存在**推斷（與 uniform 的 `spacing` 同慣例），手寫或舊 config 可無縫 round-trip
- [x] **驗收（實測）**：要求 1e-3 / 2e-4 / 5e-5 的端點間距，實得誤差 **≤0.02%** 且兩端對稱；
  geometric 單邊 5e-4 誤差 0.00%；極端粗的請求安全退化無 NaN。新增
  `tests/test_end_spacing_distribution.py`（33 checks）；全套 **33/33 PASS**

### 已完成：status bar（N10，2026-08-06）

`main_window_statusbar_mixin.py` 新增常駐狀態列，放今天**無處可去**的三項資訊：

- **Stage**：跟隨 `mode_changed`，用短名（combo 的 "PreProcessor (CAD)" 對狀態欄太長）
- **Selection**：邊數／選取的頂點，**並且一定標明屬於哪個 layer** —— 開了多個幾何時「2 edges」本身是有歧義的。今天完全沒有任何地方顯示選取數
- **Activity**：進度列**只顯示有東西在動、從不說是什麼在動**。改由既有的 `claim/set/release_progress` 三個方法驅動（所以現有與未來的所有呼叫點自動涵蓋，不需逐點修改），且**放在 owner guard 之後** —— 非擁有者不能改掉別人的標籤。未知的 owner 原樣顯示而非留白，讓新呼叫點看得見而不是靜默消失

**刻意不放的兩項**（測試會鎖住，避免日後被「順手補上」）：
- **游標座標**：三個 canvas 都已有跟著游標的 `coord_label`（而且 R9 才修過它離開時清空）。固定讀值反而不如浮動標籤，且**兩個會互相矛盾的座標顯示比一個更糟**
- **單位**：還沒有單位系統，一個永遠顯示同一件事的欄位會訓練使用者不再看狀態列

`flash_status()` 讓原本只進 log panel 的訊息（如 undo）也能在不開 log 的情況下被看到，且**不會覆蓋常駐欄位**。

`tests/test_status_bar.py`（24 checks）；全套 **36/36**。**需你實機確認**：狀態列高度與各欄位寬度。

### 建議下一步順序

1. **N8 架構部分**（單一資料流方向）— 以 `push_panel_config()` 為起點逐面板收斂；需有顯示環境互動驗證
2. **N10**（status bar）— 中型 UI，需有顯示環境驗證
3. **N9 + 單位系統** — 需獨立規劃（單位系統與 N4 同源，建議一起設計）
4. 逐步把 `ruff.toml` 的 `select` 擴到風格規則 —— **但要先修違規再加**，不要讓 gate 變回永遠紅的狀態
5. ~~值得單獨檢視：`solver/preprocess/` 底下其他「Python 寫 / C++ 讀」的介面~~ → **已稽核，見下**

### 已完成：solver para.in 漂移稽核（2026-08-06，同日第九批）

STL3d 那次是**靜默失效且 exit code 0**，所以「其他介面應該沒事」不能當成假設。把剩下兩個
「Python 寫 / C++ 讀」的介面都查了：

- [x] **getPGrid — 正確（11 個 live read 對 11 行答案）**
  - 逐行核對控制流後確認：`generate_getpgrid_para` 的順序與 `getPGrid.cpp` 完全對應，檔名都落在期待檔名的那個 read 上
  - **但發現一顆活的地雷**：source 裡有一個 `#if 0` 區塊包著 `cin >> yn48`（"Is this a quad or hex mesh?"）。它今天被編譯掉，這正是 11 個答案能對齊的原因 —— 一旦有人重新啟用，後面每個答案都會位移一格，就是 STL3d 那種靜默失效
  - 另外兩個分支相依的 read 也已釐清：Patran 的 `fn_neutral` 在 else 分支（GUI 永遠答 "y" 走 starcd，不會讀到）；`mixedf`/`slicing_yn` 只在 stifcons 答 "y" 時存在，而 writer 硬編 "y"，所以兩個都在路徑上
- [x] **bDecompose — 正確**
  - 它**只有預編譯 binary、沒有原始碼**，所以無法從程式碼讀出 stdin 順序。唯一的 ground truth 是 work 目錄裡出貨的 `para.in`；writer 的輸出與它逐行相同
- [x] **守門**：新增 `tests/test_solver_para_in_parity.py` —— 剝除 `#if 0` 後解析 `getPGrid.cpp` 的 `cin >>` 序列並逐位比對（檔名槽必須是檔名、y/n 槽必須是 y/n），`#if 0` 若被啟用則測試失敗；bDecompose 則比對出貨的參考檔
  - 寫測試時我自己踩到一個坑並修掉：用 `index("cin >> fn_bc")` 會誤命中 `cin >> fn_bcflags`（前綴匹配），必須用 `\b` 字界
- **結論：沒有新的靜默漂移。** 三個介面裡只有 STL3d 是壞的，已修

---

## 附錄 A — 建議實作順序與相依

```
Phase 0 (R1, R6, R8, R4) ── 全部獨立，可平行 ──┐
                                               ├─→ Phase 1 (R5 依賴 C++ 進度輸出；R2/R3 需 C++ 對齊)
Phase 2 (R7, R9, R10, R11) ── 獨立 ────────────┘
Phase 3 ── 依賴 R4 (format_version) 已落地
```

關鍵相依：
- R5（進度百分比）需 C++ 端先輸出可解析的進度訊息，否則只能停在 busy 動畫。
- Phase 3 的格式遷移依賴 Phase 0 的 R4 版本號先到位。
- R2/R3 牽涉 GUI 與 C++ 雙邊，需先做去留決策再動工。

## 附錄 B — 已駁回的誤判（勿重工）

| 宣稱 | 位置 | 判定 |
|------|------|------|
| VTK 解析 off-by-one，應為 `k+2` | `models/vtk_mesh.py:57` | **誤判**：刻意丟棄 z，`k+1<len` 守衛正確 |
| `RemoveSplitCmd` 索引位移錯誤 | `commands/split_cmds.py:60` | **誤判**：刪頂點後 `[2,8]→[2,7]` 正確 |
| signal 連線指數洩漏 | `controllers/backend_ctrl.py:193` | **誇大**：每次建立全新 worker，各自持有訊號 |
| transform 從不存檔 | `models/project.py` | **誤判**：`backend_ctrl.py:180` 匯出前才設定 |
| 無 dirty flag / 無未存提示 | — | **誤判**：`controller.py:414`、`session_ctrl.py:99` 皆有守衛 |
| CleanDoubleSpinBox locale 不一致 | `views/clean_double_spin_box.py` | **非 bug**：顯示/解析同 locale，儲存走 `.6g` C-locale |
| STL header `n` 損毀致除法錯誤 | `services/stl_loader.py` | **誤判**：`_is_binary_stl` 已用檔案大小驗證 n |
