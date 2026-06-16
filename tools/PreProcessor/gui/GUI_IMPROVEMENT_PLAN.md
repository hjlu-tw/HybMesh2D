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
  - [ ] 殘留小缺口（**未做，低優先**）：非 uniform 策略（tanh/geometric）的 `spacing_start/end` 仍未在 UI 暴露
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
- [ ] **幾何統計面板**（**未做 — 中型 UI，建議獨立進行**）：點數/段數/邊界框/弧長即時顯示，需新 panel 與訊號接線，且需有顯示環境互動驗證
- [ ] **畫布工業工具**（**未做 — 大型互動 UI**）：量測/座標輸入/grid snap/視角歷史，需大量互動測試，不宜在無顯示環境盲改
- [ ] **檔案完整性 hash**（**未做 — 小型，可後續補**）：workspace 記錄輸入 `.dat`/`.stl` 的 hash，偵測外部變動
- [ ] **批次處理**（**未做 — 大型功能**）：job queue 多幾何批次跑 mesh + 整體進度

> **Phase 3 範圍說明**：自動存檔/復原（資料安全、與 Phase 0 同主題）與格式遷移地基已完成。其餘為大型 UI／跨元件（含 C++）功能，且在無顯示環境下無法互動驗證——為避免將未經實機測試的功能倉促併入，標記為待獨立進行，並附上理由。

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
