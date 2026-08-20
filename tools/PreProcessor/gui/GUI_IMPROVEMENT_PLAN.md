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
- [x] **單位系統**（2026-08-07）—— 見下方專節
- [x] **幾何統計面板**（2026-08-06）：CAD sidebar 新增「Geometry Statistics」摺疊區（預設收起 —— sidebar 固定 360px，edge properties 優先）
  - `services/geometry_stats.py`（Qt-free）：點數/段數/開閉/bbox/範圍/周長/間距 min-mean-max/**均勻度**
  - **最有價值的是均勻度**：相鄰間距的最大擴張比。超過 1.2× 會讓 BL 長得很差，而在此之前只能「產生網格看它爆掉」才發現。門檻與 `.dat` quality heatmap 一致，兩者不會互相矛盾
  - 擴張比**方向無關**（2× 驟縮與 2× 驟增同樣糟），並回報最差處**位於哪個點**，讓數字可行動而非只是判決
  - **閉合幾何把接縫段納入**周長與比值統計 —— 那是真實的網格邊，而最差的跳變常常正好在接縫
  - 退化輸入（空/單點/全 NaN/全重複）回 `{}` 而非捏造 0，UI 顯示「—」；非有限點被丟棄而非傳播
  - 只有均勻度那一列會變色（那是唯一帶「判斷」而非「量測」的數字）；清空 sidebar 時歸零，不留上一個幾何的數字
  - `tests/test_geometry_stats.py`（26 checks）；全套 **35/35**
  - **需你實機確認**：摺疊區的位置與字級（我只能驗證數值與變色邏輯，不能驗證好不好看）
- [x] **畫布工業工具**（2026-08-06）：`services/canvas_tools.py`（Qt-free 邏輯）＋ `views/canvas_tools_mixin.py`（canvas 狀態與疊圖）＋ CAD 工具列控制項
  - **量測**：兩次點擊讀出距離 / dx / dy / 角度（從 +x 軸起算，(-180,180]）。先前要檢查 slat 縫寬、弦長、或 BL 能塞進多少間隙，都得把幾何匯出到別處算
    - 量測點也走同一套 snap（量兩個幾何點之間的距離是最常見用途）
    - 完成一段後**下一次點擊開始新的一段** —— 沿著多元件縫隙逐段量測時，強迫重新啟用工具只是白費摩擦
    - 關掉工具後**保留最後一段** —— 數字關掉工具後仍值得讀
    - 點擊在選取/hit-test **之前**被攔截，所以量測不會順手改變選取
  - **grid snap**：組合進既有的 `snap_cb`（所以放置點擊、即時預覽、handle 拖曳全都涵蓋）。**端點吸附優先於格線** —— 若格線無條件最後套用，會把剛焊上的端點又拖離幾何，靜默重開使用者剛關上的縫。這個順序有專門測試鎖住
  - **視角歷史**：back/forward。連續近似的視角會被合併（pyqtgraph 每一格滾輪都發一次 range change，逐一記錄會讓「上一個視角」變成「退一個像素」）；從歷史中途再導航會截斷 forward 分支（與瀏覽器/CAD 一致）；還原時不記錄自己
  - **座標輸入**查證後**本已存在**（`move_x`/`move_y`/`move_btn` 移動選定頂點），不重做
  - **過程中我自己踩到兩件事**：先寫了 `grid_snap_step_value` 鏡像（一個量兩個來源，正是 N8 批評的模式）已刪除，直接讀 spin box；游標設定用了 `except Exception: pass`，被 **N7 的靜態 gate 當場擋下**，改為 `_log.debug(exc_info=True)`
  - `tests/test_canvas_tools.py`（64 checks）；全套 **38/38**
  - **需你實機確認**：量測疊圖的字級/位置、工具列新增 5 個控制項後的擁擠程度
- [x] **檔案完整性 hash**（2026-08-06）：workspace 每個 session 記錄 `source_fingerprint`（size + mtime + SHA-256），載入時比對並回報
  - 問題本質：workspace 存的是幾何**點陣列**＋來源路徑，兩者脫節時沒人發現。若 `.dat`/`.stl` 在存檔後被重新匯出/腳本重生/手改，重開時 canvas 顯示**存檔時的點**、而 mesh 階段**重讀磁碟上的新檔** → 網格是使用者沒看過的幾何
  - 刻意只**回報**不阻止：磁碟上的檔案可能才是新的事實，由使用者決定
  - 成本：256MB STL 雜湊約 1 秒，而 autosave 每 60 秒跑一次 → `fingerprint()` 接受前次記錄，size+mtime 未變就重用 digest（實測確認不重算）
  - 分級：`ok` / `changed` / `missing` / `unverified`（無記錄或版本較新 → unverified，**絕不誤判為 mismatch**）
  - 已知界限並誠實記錄在測試中：size+mtime 都被偽造成相同時，快路徑會判 ok；任何真實編輯都會改變其中之一
  - `tests/test_file_integrity.py`（19 checks）；全套 **34/34**
- [x] **批次處理**（2026-08-06）：`services/batch_runner.py`（Qt-free）＋ `run_batch.sh` / `run_batch.py`
  - 三個「因為批次是你放著跑的東西」而最重要的性質，每一個都有測試鎖住：
    - **一個壞案例不能拖垮整個佇列**：失敗記錄下來、下一個繼續。因為第 3/40 個案例的 domain 反了就終止整夜的工作，正是讓人不再用批次模式的行為。非 `PipelineError` 的意外例外同樣不中斷，但會明確標為 unexpected 而非當成一般階段失敗
    - **各案例不能互相覆蓋**：輸出路徑由 case name 衍生，同名就會靜默互相蓋掉。碰撞在**任何東西開始跑之前**就偵測並回報，而且**回報的是來源檔名**（`case_b.json, case_dup.json`）而非把共用的名字複述一次 —— 後者不告訴使用者該去改哪個檔
    - **exit code 只有全部成功才是 0**：「跑完但 12 個失敗」不能對 scheduler 看起來是綠的
  - 支援 `@manifest`（一行一個路徑、`#` 註解、相對路徑相對於 manifest 自身目錄）
  - `should_stop()` 在兩個 job 之間輪詢，讓 GUI 取消能停下佇列而不會殺掉正在寫檔的那個 job
  - **實測**：4 個案例（2 正常、1 domain 反轉、1 同名）＋1 缺檔 → 3 ok / 1 failed / 1 skipped、碰撞指名兩個檔案、**exit code 1**
  - 順手把 `run_pipeline.py` / `run_batch.py` 納入 CI 的 lint 範圍（先前它們在 `gui/` 之外，`ruff check .` 碰不到）
  - `tests/test_batch_runner.py`（24 checks）；全套 **37/37**

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
| N8 | 105 處 `blockSignals` + 20 處 `_is_populating` → 無單一資料流方向 | 全 views/controllers | 中 | [x] 已修（護欄 2026-08-06 + 架構 2026-08-07） |
| N9 | 零 i18n（`tr()` grep = 0），全字串硬編英文 | 全 GUI | 低 | [~] 機制完成 + 常駐介面已翻譯；面板/對話框字串未包裝 |
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
- [x] **架構部分已完成（2026-08-07）** —— 見下方專節

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

### 修正：`◀`/`▶` 視圖歷史「按一次沒反應」（2026-08-07，使用者提問時發現）

使用者問這兩個箭頭是做什麼的。查接線時發現功能是通的（縮放／平移歷史的上一步／下一步），
但**實測暴露一個真實的可用性缺陷**：三次縮放後按一次「上一步」，視圖從 `[0.396,0.604]` 只變成
`[0.395,0.605]` —— 幾乎沒動，要按兩次才真的退一步。

**根因是我自己寫的 docstring 說了謊。** `ViewHistory` 的說明寫著「近乎相同的連續視圖會被合併：
pyqtgraph 每一個滑鼠滾格都會發 range change，全部記錄會讓『上一步』變成『退一個像素』」——
但 `tol = 1e-9` 只是浮點相等容差，**那個合併從來沒有被實作**。pyqtgraph 為 x/y 各發一次訊號，
所以單一次 `setRange` 就推了兩筆只差一根頭髮的紀錄。

- [x] **容差改成「跨距的比例」**（預設 1%），而不是絕對距離 —— 顯示 2000 mm 計算域和顯示
  0.02 m 翼型的畫布需要同一個答案。零跨距退回座標量級，不會除以零
- [x] **記錄改成去彈跳**（`VIEW_PUSH_IDLE_MS = 350`）：視圖**停止移動後**才記一筆，所以一次
  滾輪縮放或一次拖曳平移是**一筆**歷史，和瀏覽器一致。還原視圖前會先 `stop()` 待發的 timer，
  否則還原本身會被記成新的一步並截斷「下一步」分支
- [x] 實測：每按一次「上一步」現在都退一整個縮放步（0.396 → 0.184 → -0.026）
- [x] 測試更新並強化（`test_canvas_tools.py`）：三個手勢必須**剛好**記三筆（不是每軸一筆）、
  「上一步」必須移動**整個手勢**的量（跨距變化 > 50%，正是原本失敗的那一點）、
  還原不得自我記錄、容差的**尺度無關性**（2000 單位跨距上的 10 單位算同一步、600 單位不算）
  - 過程中我插入的檢查污染了共用的 `h` 實例狀態，害後面兩個斷言失敗 —— 已改用獨立實例

### 修正：CAD 工具列一列放不下、文字被截斷（2026-08-07，使用者回報）

使用者回報「CAD 的上欄只有一列太擠，很多字顯示不完全」。

**根因是那個 `threshold = 1200` 是猜的數字，而且一行裡錯了兩件事：**

1. 它比較的是**視窗**寬度，但工具列比視窗窄 —— sidebar 佔掉其餘部分。1600px 的視窗只有
   1240px 的工具列
2. 硬編數字每加一個控制項就過期一次；有了 i18n 之後更糟 —— **中文標籤的寬度不等於英文的**

- [x] **改成量測，不再猜**：`_row_width()` 用 widget 自己的 `sizeHint()` + spacing + margins
  算出單列真正需要的寬度，`_row_fits()` 拿它跟**工具列**（不是視窗）的寬度比。CAD 與 Mesh 兩處
  的 threshold 都移除
  - 單列清單改成在判斷**之前**先列出來（原本定義在 `else:` 分支裡，決定完才存在），
    順帶消掉一份重複的 widget 清單
  - `cad_sep2` / `mesh_sep3` 只存在於單列排列，量測前必須先設為可見，否則每次接在雙列之後的
    量測都會少算一個分隔線的寬度
- [x] **`◀ View` / `View ▶` 縮成 `◀` / `▶`**：前後導覽的箭頭本身就是通用符號，那個 "View" 字
  只佔寬度不帶資訊，而 CAD 這一列是全 app 最擠的。單列需求 1135 → **1073**，第二列 593 → **531**
  （雙列現在能撐到 900px 視窗）
- [x] **gate（`test_ui_state_and_dialogs.py` 第 10 節）**：在 1800 / 1500 / 1300 / 1100 / 950px
  五個寬度下，**被選中的排列的每一列都必須放得下**（一列比工具列寬，就正是「字被截斷」）；
  並確認極窄視窗仍退回雙列而不是更擠的單列
  - gate 一開始**空洞地通過** —— 第 9 節把 stage 停在 IB，而 IB 工具列短到哪裡都放得下。
    已明確切回 CAD 再量
  - 反向也驗過：強制單列時 1300px 視窗需要 1073px、工具列只有 940px → 如期 OVERFLOW

**已知限制**：視窗小於約 900px 時，連雙列都放不下（兩列各需約 547 / 531px）。沒有加第三列 ——
真要處理應該是讓工具列水平捲動（如同 mesh 面板的做法），是獨立的一項工作，不在這次回報範圍內。

### 修正：畫布工具列控制項從未被放上工具列（2026-08-07，使用者回報）

使用者回報「兩個寫著 snap 跟 0.1 m 的彈出視窗，關掉主視窗後不會一起關閉」。

**這比外觀問題嚴重，而且是我先前交付時說錯了範圍。** 我當初把畫布工具（Measure / Snap /
吸附間距 / ◀ View / View ▶）列為「已完成，需實機確認工具列擁擠度」。實際情況是**這五個控制項
從來沒有被加進工具列的版面清單**：

- `main_window_toolbar_mixin` 的 CAD 版面是**逐一列舉** widget 的清單，五個都不在裡面
- 其中 `grid_snap_cb` / `grid_snap_step` 建立時**沒有 parent** —— Qt 中無 parent 的 QWidget
  **就是頂層視窗**，所以它們變成兩個浮動小窗，而且不隨主視窗關閉
- 另外三個（`create_tb_btn` 建立，有 parent）則是單純看不到、無法使用

兩半都是**靜默**的：沒有警告，widget 也確實「存在」，任何屬性測試都照樣通過。我原本宣稱
「已完成」是不對的 —— 它們當時完全無法使用。

- [x] 兩個 widget 補上 `self.canvas_toolbar` 作為 parent
- [x] 五個控制項加入 CAD 工具列的**兩種**排列（寬螢幕單列、窄螢幕雙列），放在第二列與其他檢視切換一起
- [x] **gate（`test_ui_state_and_dialogs.py` 第 9 節）**，鎖住整個 bug class 而非這一次的實例：
  1. 建好主視窗後，**唯一**可見的頂層 widget 必須是主視窗本身
  2. 每個 stage 的 `*_tb_widgets` 中的每個 widget，都必須被 `tb_layout` 定位**或**是刻意隱藏的
     （分隔線在雙列模式下隱藏）—— 「兩者皆非」就是宣告了卻沒放上去
  3. 且都不得是頂層視窗
- [x] **實測 gate 真的會抓**：暫時把 parent 拿掉重跑，第 9 節如期失敗；還原後全過

### 已完成：批次佇列 GUI（2026-08-07）

`services/batch_runner` 早就備好 `progress()` / `should_stop()` 掛勾，缺的是從 GUI 驅動、觀看、停止它的方法。

- [x] **Modeless 對話框，不是新的 stage 頁**：stage 頁（CAD → Mesh → Solver → IB → Results）是
  **同一個 case** 的步驟；批次是**跨多個 case** 的操作，不屬於那個序列。Modeless 是因為批次的意義
  就是放著讓它跑。對話框只建立一次不重建 —— 花時間組好的佇列必須在關窗後還在
- [x] **`should_stop()` 單獨用會讓 Cancel 變成謊言**：它只在 case **之間**被輪詢。這對「不留下寫一半的
  輸出目錄」是對的，但單靠它，Cancel 按下去要等到當前網格／求解跑完（數分鐘到數小時）才有反應
  - `pipeline_runner._stream` 新增 `on_process(proc)`，並貫穿每個 stage helper 與
    `run_pipeline`/`run_batch`（全部 keyword-only、預設 `None`，headless CLI 完全不受影響 —— 已實測）
  - worker 用 `proc_util.stop_process_async` 殺掉當前 child：SIGTERM→grace→SIGKILL **over the
    process group**，因為一個 stage 是**行程樹**（mpirun ranks、gmsh helpers），只殺直接 child 會留孤兒
  - **兩者都需要，不是二選一**：殺 child 停掉正在做的工作，stop flag 阻止下一個 case 開始
  - 覆蓋啟動競態：cancel 在 child 還沒生出來時抵達不能遺失（`_note_process` 註冊後重檢旗標）
  - 實測：`sleep 60` 的 child 在 cancel 後 rc = -15；先 cancel 再註冊的 child 同樣被殺
- [x] **名稱衝突在「排入佇列時」就顯示**，不是等到執行時。輸出路徑由 case name 推導，共用名稱等於
  一個 case 靜默毀掉另一個的網格。`find_collisions` 本來就回報**來源檔名**（可行動的事實），
  在加入腳本時就顯示才是還能便宜修好的時機；執行前再用 `confirm()` 擋一次
- [x] **無法讀取的腳本變成看得見的 `skipped` 列並附原因**。安靜地跑完 10 個裡的 9 個，比整批失敗更糟
- [x] 關閉走既有的 `lifecycle_ctrl._join_worker` 有界升級（批次排**第一個** —— 它是唯一可能離結束
  還有數小時的 worker）。我一開始另寫了 `stop_batch_worker`，重複，已刪
- [x] **我自己的 gate 抓到的兩件事**：i18n 覆蓋率報告指出新選單字串未翻譯；ruff 抓到簡化表格顏色
  處理後留下的死 import。另外 `show_summary` 有真實順序 bug —— `_refresh()` 會用佇列數量重寫狀態
  標籤，導致摘要在「結果最重要的那一刻」被蓋掉
- [x] `tests/test_batch_queue_gui.py`（28 checks，含用**真實 binary** 跑完兩個 case 的端到端批次）；
  全套 **42/42**

**未做**：佇列順序拖曳重排、單一 case 重試按鈕 —— 兩者都是純 UI 便利性，沒有正確性風險，
沒有先做的理由。

### 已完成：N8 架構部分 —— 單一資料流方向（2026-08-07）

**先量測，不憑感覺重寫。** 結果推翻了我對缺陷位置的假設：controller 伸手進面板 widget 讀設定值
的地方**只有 1 處**，面板封裝其實不差。真正的缺陷是**模型落後於面板** —— `global_*_config`
只在「該階段實際執行時」才更新，中間一直是舊的。而每一個繞過這個落後的作法都是一份**不同的**部分複製：

| 位置 | 當時的做法 |
|---|---|
| `_sync_global_scalars_from_panel` | 複製全部，除了一份**寫死**的排除集合 |
| `handle_mesh_config_changed` | 只複製 `geom_roles` / `group_bc`（後來加上單位）**另外三個欄位** |
| solver 模型 | **完全不更新** |
| `_collect_project_state` | 乾脆繞過模型，直接序列化面板 |

一個量、四個真相來源，每個都「在某個時刻」是對的。我自己就撞到：做單位系統時
`global_solver_config.fs_unit_re` 讀到 200，而面板顯示 2.2853e5。

- [x] **`controllers/panel_sync_ctrl.py`**：`sync_panel_to_model()` 在**每一次**使用者編輯時執行
  - 重用既有的 widget introspection（`undo_ctrl._wire_widget_edits`）—— 那是全專案唯一知道
    「使用者動了這個面板」的地方，所以也該是同步發生的地方。改為呼叫 `on_panel_edited()`：
    **先同步模型，再排 undo snapshot**（快照本來就該記錄編輯**後**的狀態）
  - 兩個 traversal 會變成兩次「覆蓋到不同 widget 集合」的機會，所以只留一個
- [x] **`PRESERVED_FIELDS`（面板不擁有的欄位）不是可選項**：solver 面板**沒有** `length_unit`
  的 widget，整份複製會把它歸零、連 `Linf` 的意義一起帶走
  - 由 `services/config_ownership.py` **用 AST** 從面板自己的原始碼推導並 gate 住 ——
    先用 regex 有假陰性：`cfg.xmin, cfg.xmax = ...` 這種 tuple 賦值抓不到，害 IB 面板一半的
    欄位看起來「沒有被寫入」
  - gate 另外斷言「擷取器真的找到相當數量的賦值」—— 我一度把來源根目錄算錯一層，glob 全部
    命中 0 個檔案，那會讓整個 gate **空洞地通過**
- [x] **`extra_preserve` 與 `PRESERVED_FIELDS` 刻意分開**：「面板無法擁有這個欄位」和
  「我現在正在改這個欄位」是兩種不同的主張。把它們混在一起，正是當初那份排除清單看起來
  像「擁有權」但其實不是的原因
- [x] **守衛必須是面板自己的旗標，不能靠呼叫端自律**（我第一版做錯並立刻被抓到）
  - 第一版靠「呼叫端有沒有用 `push_panel_config`」判斷是否在填值。這把「忘記走 funnel」的
    代價從**多記一個 undo step** 升級成**污染模型** —— 三個既有測試當場失敗
  - 改為 `set_config` 自己在 `try/finally` 裡設 `_loading`，同步檢查那個旗標。面板知道自己
    正在填值，而且不可能忘記
  - 三個面板都改成 `set_config` / `_set_config_body` 拆分，例外時旗標仍會清掉 ——
    旗標卡住 = 該面板從此**靜默地永遠不再同步**，比原本的落後更糟
- [x] **模型可定義 `normalize()`** 修復同步會破壞的自身不變量：`SolverConfig` 重新由（被保留的）
  單位推導 `linf`，因為 `linf` 有 widget 而它所依據的單位沒有 —— 否則同步**自己**會造出
  `length_unit=mm` 配 `linf=1` 的矛盾狀態，然後 `unit_check()` 會回報一個並非使用者造成的問題
- [x] **順手修掉一個既有的真實資料流失**：workspace 存檔序列化 `panel.get_config()`，
  所有「面板不擁有」的欄位都被寫成 dataclass 預設值 —— `bc_geom = symmetry` 存成 `wall`
  （單位系統上線後還會把 solver 的 mm 存成 m）。改為先同步再序列化模型，且仍然保有
  「沒跑過任何階段也能存到剛才的編輯」這個當初繞過模型的理由
- [x] `tests/test_panel_model_sync.py`（29 checks）；全套 **41/41**，lint 全綠，所有 GUI 檔案 < 500 行

**未做**：`_collect_project_state` 之外還有其他讀 `get_config()` 的地方（各階段 Run 前），
那些行為正確（Run 本來就要即時值），沒有動它們的理由。

### 已完成：長度單位系統（2026-08-07）

> 我原本把這項列為「純跨元件工程、風險高」。查了求解器手冊後**前提要修正**：這不是標示問題，
> 是**數值正確性**問題，而且錨點就寫在手冊裡。

`docs/UNICONES User Manual V0.6.pdf`：`fs_UnitRe` 是 **per meter**，`Linf` 是
「Length scale used to normalize grid coordinates (**in meter**), input 1 if dimensional in
meters」，手冊自己的範例寫 `Linf 0.0254 //to convert mesh to meter`（網格用英寸）。所以

    Re = fs_UnitRe × Linf，而 Linf 就是「1 個網格單位等於幾公尺」

**mm 幾何用預設 `Linf = 1` 跑，雷諾數就差 1000 倍，而網格圖看起來完全正常。** 這才是這一項要關掉的 bug。

- [x] **`Linf` 由宣告單位推導，不是自己填**（`SolverConfig.linf_from_unit`，新設定預設 True）
  - `load_from_dict` 對「有手填 `linf`、沒有 `length_unit`」的舊檔**關掉**推導並保留原值 ——
    否則會把一個原本跑得正確的案例的雷諾數悄悄改掉。改成由 `unit_check()` **報告**差異，
    而且講具體：「`Linf = 0.0254` 意思是英寸網格，但宣告單位是公尺，Re 差 39.37 倍」
- [x] **改單位只換標示，絕不重新縮放**。只有兩件事會動數值：`Linf`，以及**匯入時**的座標
  （`views/import_unit_dialog.py`：每次匯入動作只問一次、預設不換算、headless 靜默 no-op）
  - 匯入對話框把後果寫成數字（「座標將乘以 0.001」），而不是「將進行單位換算」—— 這是刻意破壞性的操作
- [x] **單位顯示用 spin box 自己的 `setSuffix`，不寫進 label 文字**：後綴掛在持有那個數字的
  widget 上，不會被漏掉；改寫 label 要跨五個 mixin 抓幾十個 QLabel 參照，而且以後新增欄位一定漏
  - 實測 `SciDoubleSpinBox` 與 suffix 完全相容：`1.2e-07 mm` 往返正確、含/不含後綴輸入都通過驗證、
    `specialValueText`（"auto"/"unset"）不被破壞
  - **只有物理長度有單位**；成長率、角度、層數不能有 —— 給無因次量掛單位是「看起來很權威的謊」
  - `LENGTH_FIELDS` 必須等於面板的 `SciDoubleSpinBox` 集合，`tests/test_units.py` 靜態擋住
    （N4 的規則反過來給了我一份精確清單）
- [x] **自訂單位是一等公民**：0…1 的單弦翼型網格（弦長 25.4 mm）不是公尺也不是英寸，
  就是「1 單位 = 0.0254 m」。支援它之後「Linf 由單位推導」對**每個**專案都成立
- [x] **真正的防線是把錯誤變成看得見的數字**：Solver 面板即時顯示
  `→ Re = fs_UnitRe × Linf`。手冊的 double-cone 案例精確重現 **Re = 5805**；同一個網格改宣告成 mm
  就顯示 **228.5**
  - **尺寸合理性啟發式幾乎沒用，程式碼裡直接寫明**：4500 mm 誤當 4500 m 對一艘船完全合理，
    任何寬到不會誤判的區間都抓不到它。只保留「離譜級」防線（1e-8…1e6 m），不假裝知道答案
- [x] headless：`run_pipeline.py` 印 `[INFO] model unit` 與 `[INFO] reference Reynolds number`，
  並用 `PipelineConfig.unit_warnings()` 檢查 `cads`/`mesh`/`solver` 三段是否互相矛盾（**報告不阻擋**）
- [x] **C++ 端**：`Config.hpp` 解析 `LENGTH_UNIT` / `_METRES` / `_NAME`，banner 印
  `- Model Unit`（因此也進 provenance sidecar）。**只記錄、不換算** —— 網格器只拿長度互相比較，
  換算它們只會多一個 bug 的機會。GUI↔C++ 鍵 parity 由既有 gate 擋住
- [x] 我自己踩到並修掉的兩個 bug：
  1. 用 `push_panel_config(panel, scfg)` 同步 `Linf` 會呼叫 `set_config`，把使用者剛打進 Solver
     面板的 `Unit Re` 一起覆蓋掉。衍生欄位只能改自己那一個 widget（包在 `suppress_project_undo()` 裡）
  2. `ndarray.ptp()` 在 NumPy 2.0 已移除
- [x] `tests/test_units.py`（57 checks，含用**真實已建置 binary** 驗 `LENGTH_UNIT in` → 0.0254）；
  全套 **40/40**，實跑 naca0012 網格與 headless pipeline 驗證

**未做**：`.dat`/`.stl` 匯出時不寫單位（兩種格式都沒有單位欄位；資訊留在 config/workspace/provenance 裡）。

### 部分完成：N9 i18n（2026-08-06）

> 範圍誠實說明：**機制完整可用、常駐介面（選單列 + 狀態列）已完整翻譯成繁體中文**（78/78 字串）。
> 面板欄位標籤、對話框內文、log 訊息**仍是英文** —— 那是數千個字串的機械工作，見下方「剩餘範圍」。

- [x] **呼叫端用標準 Qt**：`self.tr()` / `QCoreApplication.translate()` / `QT_TRANSLATE_NOOP()`。
  日後若裝了 `lrelease`，換成編譯式 `.qm` **不需改動任何一個呼叫點**
- [x] **後端用 JSON 目錄**（`services/i18n.py::JsonTranslator`）：`lrelease`（把 `.ts` 編成 `.qm` 的工具）
  **不在 PyQt6 wheel 裡**，強制要求它會讓翻譯在一般開發機上無法建置。JSON 目錄可 diff、可在 PR 中審閱、無建置步驟
- [x] **實測踩到一個災難級 bug 並修掉**：Qt 文件說「回傳 null QString 表示無翻譯」，但 Python 覆寫回傳 `""` 會給 Qt 一個**空**字串，Qt 把它當成有效翻譯 —— **每個未翻譯的標籤都會顯示成空白**。改為回傳英文原文。這是本項最重要的一條測試
- [x] **語言選單**（`說明 ▸ 語言`）：以**各語言自己的寫法**列出（`English` / `繁體中文`）—— 語言選單必須讓「看不懂當前介面語言的人」也能讀。切換後**下次啟動生效**：即時重譯要走遍每個 widget 重設每個字串，面板並非為此而建，承諾即時切換卻只做一半比明講需要重啟更糟
- [x] **覆蓋率工具** `tools/scripts/i18n_extract.py`：靜態掃描已包裝字串並與目錄比對，報告缺漏與過時項；`--ts` 可另外用 `pylupdate6`（**有**裝）產生標準 `.ts` 給 Qt Linguist
  - 過程中修掉工具本身兩個會**誤導人刪掉真實翻譯**的缺陷：(1) 看不懂隱式字串串接，導致目錄 key 只對到第一段、執行時永遠命中不了（這是真實 bug，已修正 tooltip 的 key）；(2) 表格內延後翻譯的字串被誤報為 stale → 改用 Qt 標準的 `QT_TRANSLATE_NOOP` 標記
- [x] `tests/test_i18n.py`（26 checks）；全套 **39/39**

**剩餘範圍**（未包裝）：`views/panels/` 的欄位標籤與 tooltip（最大宗）、`views/*dialog*.py` 的對話框、
`log_panel` 的訊息、`report_error/warning/info` 的呼叫端字串。做法已定型 —— 包裝 + 補目錄 + 跑覆蓋率工具，
純機械工作，可分批進行且每批都能用工具驗證。

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
