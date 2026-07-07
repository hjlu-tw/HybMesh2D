# Surface Resampler Pro (PreProcessor)

這是一個工業級的 2D 幾何邊界重採樣工具，旨在為 CFD 混合網格生成提供高品質的表面格點分布。它集成了樣條插值、自動分段、參數化曲線與品質監控功能。

## 核心功能

- **三次樣條插值 (Cubic Spline)**：自動將離散點擬合成平滑曲線，消除線性插值的稜角感。
- **多元素支援 (Multi-element)**：支援在單個配置中定義多個獨立幾何體（如多段翼型）。
- **CAD 幾何變換**：支援對物體進行縮放 (Scale)、旋轉 (Rotate) 與平移 (Translate)。
- **自動分段偵測**：自動識別幾何尖角並進行分段，精確保留幾何特徵。
- **間距平滑匹配 (Match Spacing)**：支援指定起始/結束間距，自動計算增長率以達成平滑過渡。
- **參數化曲線**：支援使用數學公式 $(x(t), y(t))$ 直接定義幾何。
- **品質監控**：直觀的熱向圖視覺化，自動偵測並標註不合格的格點跳躍 (Expansion Ratio > 1.2)。

## JSON 配置說明

### 頂層結構
- **`elements`**: 一個陣列，包含多個幾何元素。若不使用此陣列，則直接在根層級定義單一元素（向下相容）。

### 元素參數 (Element)
- **`name`**: 元素名稱。
- **`input_file`**: 原始幾何檔案路徑。
- **`output_file`**: 重採樣後的輸出路徑。
- **`is_closed`**: 是否為封閉迴圈（預設 `false`）。若為 `true`，會自動執行週期性閉合。
- **`transform`**: 幾何變換設定。
    - `scale`: 縮放倍率。
    - `rotate`: 旋轉角度（度）。
    - `translate`: 平移向量 `[dx, dy]`。
- **`segments`**: 線段定義陣列。

### 線段參數 (Segment)
- **`type`**: `file` (從輸入檔讀取) 或 `curve` (公式產生)。
- **`auto_split`**: 是否自動偵測尖角分段（僅限 `file` 類型）。
- **`split_threshold`**: 尖角偵測閾值（角度，預設 20.0）。
- **`formula`**: $y = f(x)$ 公式（僅限 `curve` 類型）。
- **`x_formula` / `y_formula`**: 參數化 $(x(t), y(t))$ 公式。
- **`strategy`**: 布點策略：
    - `uniform`: 均勻分布。
    - `curvature`: 基於曲率加密。
    - `cosine`: 雙端加密。
    - `geometric`: 幾何級數（等比）分布。
    - `tanh`: 雙曲線正切分布。
- **`parameters`**:
    - `n_points`: 目標點數。
    - `spacing`: 目標間距（優先級高於 `n_points`）。
    - `spacing_start` / `spacing_end`: 指定起始/結束間距（適用於 `geometric`, `tanh`）。
    - `sensitivity`: 曲率敏感度。

## 執行與視覺化

### 使用腳本一鍵執行
推薦使用專案根目錄的 `run_preprocessor.sh`：
```bash
./run_preprocessor.sh <config.json> [--quality]
```

### 品質檢查模式
加入 `--quality` 參數後，視覺化工具會以熱向圖顯示**格點擴張率 (Expansion Ratio)**：
- **綠色**：平滑過渡 ($< 1.05$)。
- **橙色**：合格 ($1.05 \sim 1.2$)。
- **紅色**：不合格 ($> 1.2$)，且會在幾何上標註紅色 `x`。

## 沉浸固體前處理：STL → φ（GUI「Immersed Boundary (φ)」模式）

UNICONES 求解器以沉浸邊界法 (IBM) 處理固體，需要一個 **phi 標記場**（0 = 流體、1 = 固體）。GUI 的 **Immersed Boundary (φ)** 模式（分頁選單，原名 Immersed Solid (STL→Phi)）包裝了 `solver/preprocess/STL3d`，把「載入 STL → 設定卡氏網格 → 射線追蹤產生 phi → 驗證」整合進互動式 3D 介面（pyqtgraph OpenGL，需 `PyOpenGL`）。

啟動後在右上模式選單切到 **Immersed Boundary (φ)**：

```bash
python3 tools/PreProcessor/gui/main.py
```

操作流程：

1. **STL Input** — 按 `…` 載入 STL。自動偵測 ASCII/binary、顯示三角面，並以邊界框 +10% 自動框出卡氏域。
2. **Cartesian Domain** — 六個 min/max 欄位定義卡氏域；`Fit to STL` 一鍵套用邊界框（margin % 可調）。3D 視窗的 domain box 與格線會隨欄位**即時更新**。
3. **Grid Resolution** — Nx/Ny/Nz；面板即時顯示 $dx, dy, dz$ 與總 cell 數（平面案例用 Nz=2、$dz=0$）。
4. **Search Method** — 全元素（穩健、較慢）或近 x-range（較快，均勻面網格適用）。
5. **Generate phi** — 背景執行 STL3d（進度條 + log）。完成後 3D 顯示固體 cell（紅），可勾選流體 cell、用 `k=` 隔離單一 z 層做驗證；log 會回報固體佔比，全為 0 時警告（通常是 domain 範圍或單位未包住 STL）。

輸出：`results/stl3d/<case>/<case>_phi_tec.dat`（Tecplot POINT 格式，每行 `x y z phi`）。

### 從 2D CAD 匯出 STL（Export 2D STL）

不必外部 CAD：在 PreProcessor 分頁畫好 2D 封閉輪廓後，側欄底部 **Export 2D STL** 會把輪廓三角化成平面 (z=0) STL 供本頁載入。當開啟中、含幾何的圖層有兩個以上時，會先跳出**來源選擇**對話框，讓你勾選哪些圖層納入這個沉浸固體 STL——避免把只想拿去產生網格的幾何一起掃入（可見圖層預設勾選，附 All / None）。

### 一鍵帶入求解器 (Send to Solver)

phi 場是**透過初始條件 DLL** 餵進求解器的。成功產生 phi 後，**Send to Solver →** 按鈕啟用，按下會自動：

1. 將 phi 去除 Tecplot 標頭，寫成 `<case>_phi.dat`（`x y z phi`）。
2. 產生會讀取它的初始條件 DLL：STL3d 的卡氏網格規格直接烤入，對求解器網格點做 O(1) 最近格點索引（原始碼存於 `results/solver/dll_src/ibm_init_<case>.cc`）。
3. 在 Solver 設定開啟 `immersed_solid`、接好 init DLL 與 phi 檔路徑，並切到 **Solver** 分頁。

之後設定好網格（`.vrt/.cel/.bnd`）按 Run Solver 即可：跑求解時 phi 檔會自動 staging 成 work 目錄的 `phi.dat`，DLL 也會自動以求解器相同旗標編譯。

## IBM DLL Builder（GUI 內產生 / 編譯 IBM DLL）

求解器的兩種使用者 DLL —— 初始條件 `initQ_at_p()` 與固體運動 `get_6dof_vel()` —— 可直接在 GUI 內產生，無需手寫 C++。在 **Solver** 模式展開 **Immersed Boundary (IBM)** 區塊，於 `init DLL` / `motion DLL` 欄位按 **Build…** 開啟：

- **Tier 1（參數模板）**：選模板（靜止 / 剛體旋轉 / 平移 / 旋轉圓盤 / 自由流 / 自訂），填參數，按 `Generate Code` 產生 C++。
- **Tier 2（程式碼編輯器）**：產生的原始碼可自由編輯（含 C++ 語法高亮）。
- **Compile**：以與求解器**完全相同的旗標**（`g++ -D_INCLUDE_TEMPLATE_IMPLEMENTATION -fPIC -shared -O3`）試編，行內顯示 `file:line:col` 診斷（雙擊跳到該行）。
- **Save & Use**：存成 `.cc` 並自動填回欄位；求解 pipeline 執行時會把它編進該 case 的 `dll/`。

> 注意：產生的 `extern "C"` 簽章是與求解器的契約，集中維護於 `app/services/dll_templates.py`（求解器若改簽章，只需改這一處）。需要編譯器（g++/clang++）在 PATH 上；找不到時 Compile 會停用，但求解器仍會在執行時自行編譯 `.cc`。

## 結果後處理 (Results)

載入求解器的 Tecplot 輸出（`xtecp_sol_allz.dat.*`）後，**Results** 分頁提供互動式場視覺化（FEQUADRILATERAL zone 會在載入時切成兩個三角形）：

- **場繪製**：填色 (tripcolor) 或平滑等值填色 (tricontourf)；變數 / zone / 繪製模式選擇；色階（colormap、對數 / 對稱、連續或分段）。頂欄 **Contour** 可關閉場填色，只保留疊加層。
- **疊加層**：網格線框、速度流線、向量箭頭、等值線 (iso)。
- **CAD 幾何疊加**：把目前專案開啟的幾何輪廓疊到場上。可**逐一勾選**要顯示的幾何（單個或多個），並從一小組線色選擇（White / Gray / Black / Cyan / Amber / Green / Pink / Red）。
- **探針工具**：點查詢 (probe，列出該點所有變數)、沿線取樣 (line probe，另開圖表)、標註場的最小 / 最大值、面積加權統計 (∫dA / 平均 / 標準差)。
- **視圖**：滾輪縮放、右鍵 / 中鍵拖曳平移；重新載入結果或切換 zone **不會自動 fit**（保留目前縮放），需要時按 **Fit View**。
- **Wall Qty…**：開啟壁面量沿線圖 (WallForce.dat / vsurface_qty.dat …)。
- **Save PNG** 匯出目前畫面。

> 大型網格效能：`Mesh Statistics` 的品質指標（aspect ratio / skewness）已向量化，且大網格會在背景執行緒計算（不阻塞 UI）；網格畫布的線框抽取亦向量化，元素填色超過門檻的極大網格會略過（保留線框）。

## 範例檔案
- `config/comprehensive_example.json`: 基礎功能綜合展示。
- `config/industrial_pro_example.json`: 專業翼型布點與品質監控展示。
- `config/multi_element_example.json`: 多物體並行處理展示。

## 測試 (Tests)

GUI 的 undo/redo 命令層有回歸測試，位於 `tools/PreProcessor/tests/`（皆為可直接執行的腳本，路徑以檔案自身位置解析，可從任何 cwd 執行）：

- **`test_undo_redo.py`** — headless，不需 Qt / 顯示器（CI 安全）。以輕量 fake session 直接操作 command 與 model，涵蓋：以物件識別追蹤 segment 造成的「幽靈 edge」、`is_geometry_modified` 還原、每段邊界條件 (`bc`) 的 undo/redo、split 保留頂點時的 dirty 旗標、`ToggleMatchPrevious` 對不存在 segment 的行為、`ReplacePointsCmd` 共用基底、以及反覆 undo↔redo 循環的忠實度。
- **`smoke_undo_redo.py`** — offscreen GUI 冒煙測試，需 `PyQt6` + `pyqtgraph`（不需顯示器；使用 `QT_QPA_PLATFORM=offscreen`）。啟動真實 `AppController` + `MainWindow`，載入 `examples/geometries/naca0012.dat`，透過實際 controller 方法驅動 undo/redo 並檢查工具列按鈕狀態。不進事件迴圈、不觸發 modal 對話框，因此不會卡住。

```bash
python3 tools/PreProcessor/tests/test_undo_redo.py     # 快速、無需顯示
python3 tools/PreProcessor/tests/smoke_undo_redo.py    # offscreen GUI 端到端
```
