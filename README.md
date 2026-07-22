# HybMesh2D

HybMesh2D 是一個用於生成 2D 混合網格（Hybrid Mesh）的 C++ 工具。它能夠在幾何邊界周圍生成高品質的邊界層（四邊形網格），並在遠場自動填補非結構化（三角形網格）。

## 核心功能

- **邊界層生成**：根據給定的幾何形狀（如 NACA0012 翼型），向外生長指定層數與增長率的四邊形邊界層網格。
- **多幾何支援**：支援同時輸入多個不相交的幾何形狀，並分別生成邊界層。
- **加密種子 (Refinement Seeds)**：可將指定幾何標記為「加密種子」（類似 Pointwise source），僅用來設定局部最小網格尺寸、向外加密遠場非結構三角網格，**不生長邊界層、也不作為計算域邊界**。支援 `source`（純尺寸來源，網格不貼合）與 `embed`（網格節點貼合種子曲線）兩種模式，可同時指定哪些幾何為 body-fitted 邊界、哪些為種子。詳見下方「加密種子」。
- **混合網格架構**：結合近場的結構化特性（邊界層）與遠場的非結構化彈性（三角形）。
- **扇形網格 (Fan Elements)**：在幾何尖角處自動生成扇形網格以維持網格品質。
- **凹角處理與平滑**：提供凹角合併與拉普拉斯平滑技術，處理複雜幾何的網格交叉問題。
- **安全性檢查**：自動偵測幾何是否相互重疊或超出計算域邊界。
- **Gmsh 整合**：利用 Gmsh SDK 進行穩健的遠場三角化處理。
- **多格式輸出**：支援匯出 `.vtk` (ParaView)、STAR-CD (`.vrt`, `.cel`, `.bnd`)，以及 **CGNS** (`.cgns`，非結構化區 + 每 BC patch) 格式。
- **幾何關聯 (Geometry Association)**：前處理器在重採樣 `.dat` 旁產生 `.meta` sidecar，無損攜帶每點的來源段 (`seg_id`)、結構角點 (`is_corner`)、每段邊界條件 (`bc`) 與曲線型別 (`curve_kind`)。詳見下方「幾何 metadata sidecar」。
- **解析邊界層法向**：在 line/circle 表面以精確解析法向生長邊界層 (取代有限差分)，對曲面 (圓柱、前緣) 更準確。可由 `BL_USE_ANALYTIC_GEOM` 開關，預設關閉。
- **每段邊界條件**：可在 GUI CAD 檢視器逐段指定 BC，透過 sidecar 帶到 mesher，取代全域 `BC_GEOM` 的位置反推。匯出時邊界條件由「邊自帶的標籤」決定（矩形邊、自訂外框每段、幾何每段），不再靠座標反推；同名邊界自動合併為同一 group（對齊 STAR-CCM+/Fluent 的具名邊界）。
- **自訂計算域外形 (Custom Domain)**：計算域外框可用矩形 (`DOMAIN_X/Y_MIN/MAX`)，或指定一條封閉多邊線 (`DOMAIN_FILE`)。多邊形、圓、扇形皆以重採樣多邊線表示，直接走完整的邊界層/碰撞/匯出管線；外框每段可由 sidecar 帶各自的 BC。
- **內部網格 / 內流 (Internal Flow)**：可對封閉 CAD 幾何生成「內部」網格 —— 邊界層往**內**生長、三角形填滿內部核心，且不建立獨立遠場外框 (`DOMAIN_FILE <path> bl`)。域內可再放障礙物島嶼形成環狀域。
- **逐幾何角色 (Per-geometry Role)**：每個幾何可獨立選擇生長邊界層 (`bl`)，或不長邊界層、以遠場尺寸貼合 (`nobl`)。生長方向為確定性：計算域壁面往內、障礙物往外（不再用面積啟發式猜測）。
- **完整流程管線 (Full Pipeline)**：以單一 JSON 腳本一鍵串起 CAD 重採樣 → 網格生成 → UNICONES 求解 → 結果 contour。GUI 提供 **▶ Run All** 按鈕，headless 提供 `run_pipeline.sh`（無視窗、直接輸出 contour PNG），兩者共用同一份腳本與階段邏輯。詳見下方「完整流程管線」。

## 網格架構與過渡機制

HybMesh2D 將整個計算域劃分為三個主要概念區域，並實現了平滑的尺寸過渡：

1. **幾何邊界 (Geometry Boundary)**
   - 使用者輸入的幾何形狀。在外部流場計算中，內部視為「洞」，網格生成的起點即為此邊界。

2. **邊界層區域 (Boundary Layer Region)**
   - 緊貼幾何邊界向外生長的結構化區域，由**四邊形 (Quadrilaterals)** 組成。
   - 透過設定檔控制第一層高度、增長率、總層數，以及尖角處的扇形分割數量。

3. **遠場與過渡區域 (Far-field & Transition Region)**
   - 從邊界層最外圈延伸至計算域外部邊界的空間，由 Gmsh 生成的**三角形 (Triangles)** 組成。
   - **過渡機制**：程式會自動擷取邊界層最外層的高度，並以此作為 Gmsh 的起始尺寸，配合 `FARFIELD_GROWTH_RATE` 平滑放大至 `FARFIELD_MESH_SIZE`。

## 系統需求

- **編譯器**: 支援 C++17 的編譯器 (如 GCC, Clang, MSVC)。
- **建置工具**: CMake 3.10+。
- **外部依賴**: [Gmsh SDK](https://gmsh.info/)。
- **選用依賴**: [CGNS](https://cgns.github.io/) (含 HDF5)。CMake 會自動偵測；找得到才編入 CGNS 輸出，找不到時 `exportCGNS` 退化為 no-op，預設 build 不受影響。macOS 安裝：`brew install cgns`。

> ⚠️ **CGNS 與 Gmsh 的連結順序**：`libgmsh` 內部靜態包了一份 32-bit `cgsize_t` 的 CGNS 並匯出 `cg_*` 符號。CMakeLists 已確保 `libcgns` 連結排在 `libgmsh` 之前，使 `cg_*` 綁定到正確的 64-bit homebrew libcgns；請勿調換此順序。

## 編譯方式

本專案支援使用 CMake 進行建置，這會同時編譯主程式 `HybMesh2D` 與前處理工具 `surface_resampler`。

### 使用 CMake (推薦)

```bash
mkdir build
cd build
cmake ..
make
```

編譯完成後，執行檔將位於 `build/` 目錄下。

## 執行方式

```bash
./HybMesh2D [options]
```

### 常用命令列參數

- `-conf <path>`: 指定背景參數設定檔路徑（預設: `config/Background_para.dat`）。
- `-geom <path1> [path2]...`: 指定一個或多個幾何資料檔（生長邊界層的 body-fitted 邊界 / 障礙物）。
- `-geom_nobl <path1> [path2]...`: 指定不生長邊界層的幾何（以遠場尺寸貼合，作為洞）。
- `-domain <path>`: 指定計算域外框幾何（一條封閉多邊線），取代矩形外框。
- `-domain_bl`: 將 `-domain` 幾何視為計算域壁面、邊界層往內生長（= 內流）；省略時為遠場外框（外流）。
- `-seed <path1> [path2]...`: 指定一個或多個「加密種子」幾何檔（僅驅動局部最小尺寸，不生長邊界層）。
- `-seed_size <值>` / `-seed_radius <值>` / `-seed_mode <source|embed>`: 全域種子尺寸 / 影響半徑 / 模式預設值。
- `-out_vtk <0|1>`: 是否輸出 VTK 檔案 (1: 開啟, 0: 關閉)。
- `-out_starcd <0|1>`: 是否輸出 STAR-CD 檔案。
- `-out_cgns <0|1>`: 是否輸出 CGNS 檔案 (需 build 時偵測到 CGNS 函式庫)。

### 執行範例 (使用範例檔)

```bash
./HybMesh2D -conf examples/config/test_box.dat -geom examples/geometries/naca0012.dat
```

## 設定檔參數說明 (`Background_para.dat`)

### 1. 計算域與基礎尺寸 (Domain & Size)

| 參數名稱 | 說明 | 預設值 |
| :--- | :--- | :--- |
| `DOMAIN_X_MIN` / `MAX` | 矩形計算域 X 軸範圍（`DOMAIN_FILE` 未指定時使用） | -10.0 / 10.0 |
| `DOMAIN_Y_MIN` / `MAX` | 矩形計算域 Y 軸範圍 | -10.0 / 10.0 |
| `DOMAIN_FILE <path> [bl\|nobl]` | 自訂計算域外框（封閉多邊線）。`nobl`(預設)=遠場外框(不長 BL, 外流)；`bl`=域壁面(BL 往內長, 內流)。 | (無, 用矩形) |
| `GEOM_FILE <path> [bl\|nobl]` | 幾何/障礙物。`bl`(預設)=生長邊界層；`nobl`=不長 BL、以遠場尺寸貼合。 | — |
| `SURFACE_MESH_SIZE` | 表面初始網格尺寸 | 0.02 |
| `AUTO_SURFACE_SIZE` | 是否自動計算起始表面尺寸 (0: 關閉, 1: 開啟) | 1 |
| `FARFIELD_MESH_SIZE` | 遠場最大網格尺寸 | 1.0 |
| `FARFIELD_GROWTH_RATE` | 從邊界層到遠場的尺寸增長率 | 0.1 |

### 2. 邊界層核心設定 (Boundary Layer Core)

| 參數名稱 | 說明 | 預設值 |
| :--- | :--- | :--- |
| `BL_INITIAL_THICKNESS` | 邊界層第一層高度 | 0.0002 |
| `BL_GROWTH_RATE` | 邊界層增長率 | 1.1 |
| `BL_LAYERS` | 邊界層總層數 | 5 |

### 3. 尖角與凸角處理 (Fan & Convex Handling)

| 參數名稱 | 說明 | 預設值 |
| :--- | :--- | :--- |
| `BL_CONVEX_METHOD` | 凸角處理方法 (0: 扇形網格, 2: 平行四邊形) | 0 |
| `BL_FAN_NODES` | 尖角處扇形分割數量 | 5 |
| `BL_AUTO_FAN_NODES` | 是否自動計算尖角扇形數量 (0: 關閉, 1: 全域, 2: 局部) | 1 |
| `BL_FAN_ANGLE_THRESHOLD`| 觸發扇形網格的轉角閾值 (度) | 60.0 |
| `BL_CONVEX_ANGLE_THRESHOLD`| 視為凸角的外角閾值 (度) | 220.0 |
| `BL_PARA_FALLBACK_ANGLE`| 觸發雙平行四邊形策略的轉角閾值 (度) | 300.0 |

### 4. 凹角處理 (Concave Handling)

| 參數名稱 | 說明 | 預設值 |
| :--- | :--- | :--- |
| `BL_CONCAVE_METHOD` | 凹角處理方法 (0: 節點合併, 5: 厚度擴散混合) | 5 |
| `BL_CONCAVE_ANGLE_THRESHOLD`| 視為凹角的外角閾值 (度) | 120.0 |
| `BL_CONCAVE_INFLUENCE_MULTIPLIER`| 凹角平滑影響半徑倍率 (Method 5) | 5.0 |
| `BL_MERGE_CONCAVE` | 是否執行強制凹角合併 (0: 關閉, 1: 開啟) | 0 |
| `BL_SMOOTHING_ITERS` | 拉普拉斯平滑迭代次數 | 0 |

### 5. 遠場過渡與 Gmsh (Transition & Gmsh)

| 參數名稱 | 說明 | 預設值 |
| :--- | :--- | :--- |
| `BL_TRANSITION_LAYERS` | 從邊界層到遠場的過渡層數 | 3 |
| `BL_AUTO_TRANSITION_LAYERS`| 自動計算過渡層數 (0: 關閉, 1: 全域) | 0 |
| `BL_TRANSITION_GROWTH_RATE`| 過渡層尺寸增長率 | 1.15 |
| `BL_TRANSITION_BUFFER` | 過渡區域緩衝倍率 | 2.0 |
| `GMSH_ALGORITHM` | Gmsh 網格生成演算法 (預設 6: Frontal-Delaunay) | 6 |
| `GMSH_OPTIMIZE` | 是否開啟 Gmsh 網格優化 | 1 |
| `BL_USE_ANALYTIC_GEOM` | 在 line/circle 表面以解析法向生長 BL (需 `.meta` sidecar；對 smooth/polyline 無作用) | 0 |

### 6. 輸出與進階功能 (I/O & Advanced)

| 參數名稱 | 說明 | 預設值 |
| :--- | :--- | :--- |
| `EXPORT_VTK` | 是否預設輸出 VTK 格式 (0/1) | 1 |
| `EXPORT_STARCD` | 是否預設輸出 STAR-CD 格式 (0/1) | 0 |
| `EXPORT_CGNS` | 是否預設輸出 CGNS 格式 (0/1；需 build 時有 CGNS 函式庫) | 0 |
| `ENABLE_COLLISION_DETECTION`| 是否開啟多幾何體碰撞偵測 (0/1) | 1 |
| `BC_XMIN` / `XMAX` | STAR-CD 邊界名稱設定 | inlet / outlet |
| `BC_YMIN` / `YMAX` | STAR-CD 邊界名稱設定 | inlet / outlet |
| `BC_GEOM` | STAR-CD 幾何表面邊界名稱 | wall |
| `OUTPUT_FILENAME` | 指定輸出的檔案基本名稱 | (空) |

### 7. 加密種子 (Refinement Seeds)

將幾何作為「加密種子」而非 body-fitted 邊界：種子僅在其周圍驅動局部最小網格尺寸（Gmsh Distance + Threshold 尺寸場），**不生長邊界層、也不作為計算域邊界**。適合在尾流、剪切層等區域做局部加密（類似 Pointwise 的 source）。

| 參數名稱 | 說明 | 預設值 |
| :--- | :--- | :--- |
| `SEED_FILE <path> [size\|auto] [radius] [mode]` | 指定一個種子幾何檔。可選：`size` 種子處最小尺寸、`radius` 影響半徑、`mode`（`source`/`embed`）。`size` 與 `radius` 彼此獨立；若要「size 自動、radius 指定」，size 欄位填 `auto`（例：`SEED_FILE f auto 1.0 source`）。省略則套用下方全域預設 | — |
| `SEED_SIZE` | 全域種子最小尺寸預設（省略/<0：**依該 seed 幾何自身重採樣後的平均點距**自動推得，貼合其 surface point 分布） | auto |
| `SEED_RADIUS` | 全域影響半徑預設（省略：**約 100×size**；半徑外平滑回到遠場尺寸）。可獨立於 size 指定 | auto |
| `SEED_MODE` | 全域模式預設。`source`：純尺寸來源、網格**不貼合**；`embed`：網格節點**貼合**種子曲線（仍不生長邊界層） | source |

`SEED_FILE` 的數值/關鍵字順序可容忍（`source`/`embed` 可出現在任意位置）。範例：

```
GEOM_FILE examples/geometries/naca0012.dat        # body-fitted 邊界
SEED_FILE examples/geometries/wake.dat 0.02 1.0 source   # 尾流加密種子
```

命令列：

```bash
./HybMesh2D -geom naca0012.dat -seed wake.dat -seed_size 0.02 -seed_radius 1.0 -seed_mode source
```

也可在 GUI 前處理器的 **Mesh Generator → Domain & Geometry** 選取任一幾何檔，切換其角色（Boundary / Seed）並設定種子尺寸、影響半徑與模式；種子在畫布上以虛線橘色顯示。

## 視覺化與輸出

1. **VTK 格式**: 生成 `Results/*.vtk`，建議使用 [ParaView](https://www.paraview.org/) 檢視。
2. **STAR-CD 格式**: 生成一組三個檔案：
   - `.vrt`: 節點座標。
   - `.cel`: 單元（包含三角形與四邊形）定義。
   - `.bnd`: 邊界條件定義，包含設定的 BC 名稱（幾何邊優先採用 sidecar 的每段 `bc`，否則退回 `BC_GEOM`）。
3. **CGNS 格式** (選用): 生成 `*.cgns`（非結構化單一區，含三角/四邊單元 section 與每個 BC 一組 BAR_2 edge section + `BC_t` patch；BCType 對應 wall/inlet/outlet 等）。適合無損交給支援 CGNS 的求解器。可用 `cgnscheck` 驗證。

## 幾何 metadata sidecar（幾何關聯）

前處理器 (`surface_resampler`) 在真實匯出時，會於重採樣 `.dat` 旁寫一個同名 `.meta` sidecar（純文字、`ifstream` 即可解析，mesher 不需 JSON 相依）。它無損攜帶 `.dat` 純座標無法表達的資訊：

- `seg_id`（每點來源段）、`is_corner`（結構角點，供 BL 信任）、`piece_breaks`（不連續片段）。
- 每段 `bc`（邊界條件，可由 GUI 逐段指定）與 `curve_kind`（`line`/`circle`/`smooth`/`polyline`）。

mesher 讀取 sidecar 後：以 `bc` 指派幾何邊界條件（取代位置反推）、用角點旗標處理 fan/merge、並在 `BL_USE_ANALYTIC_GEOM` 開啟時依 `curve_kind` 由實際表面點重建解析曲線 (`include/Curve.hpp`) 查詢精確法向/曲率。

向後相容：缺 sidecar、欄位或舊格式時，一律退回原有行為。預覽 (preview) 仍使用 `nan` 分隔列、不寫 sidecar。

## 周邊工具 (Tools)

### 表面重採樣工具 (Surface Resampler)

本專案提供了一個 `PreProcessor` 工具，用於對幾何邊界進行分段重採樣，以便更精細地控制網格分佈。

- **核心功能**: 支援均勻分佈、餘弦分佈等策略對幾何邊界進行重新布點。
- **使用流程**:
  1. 使用 GUI 界面 (`tools/PreProcessor/gui/main.py`) 定義幾何分段。
  2. GUI 會生成一個 `.json` 設定檔。
  3. 使用 `surface_resampler` 讀取 JSON 並執行重採樣。

詳細說明請參考：[tools/PreProcessor/README.md](tools/PreProcessor/README.md)

### 沉浸固體前處理與 IBM DLL Builder (GUI)

PreProcessor GUI 另提供 UNICONES 求解器的沉浸邊界 (IBM) 前處理：

- **Immersed Solid (STL→Phi)** 模式：載入 STL、設定卡氏域（3D 即時預覽）、射線追蹤產生 phi 標記場並切片驗證；**Send to Solver →** 一鍵把 phi 帶入求解器（自動產生讀取 phi 的初始條件 DLL 並開啟 IBM）。
- **IBM DLL Builder**：在 GUI 內以參數模板或程式碼編輯器產生 / 編譯初始條件與固體運動 DLL（`initQ_at_p` / `get_6dof_vel`），編譯旗標與求解器一致。

完整操作流程見 [tools/PreProcessor/README.md](tools/PreProcessor/README.md)。

### Mesh Generator GUI 工作流

Mesh Generator 分頁以**單一幾何清單**管理輸入：用 `Add All`（加入所有已匯出的 PreProcessor session）、`Add Active`、`Browse` 加入，`Remove` 移除。清單中選取一個幾何後，以「**Role**」下拉指定角色（對應上方 CLI / 設定的 `bl|nobl`、`DOMAIN_FILE`）：

| Role | 意義 |
| :--- | :--- |
| Boundary (grows BL) | 生長邊界層的物體 / 障礙物（外流障礙物或內流島嶼）|
| No-BL (far-field size) | 不長 BL、以遠場尺寸貼合的邊界 |
| Seed (refinement source) | 加密種子（只驅動局部尺寸）|
| Domain: far-field (no BL) | 此封閉幾何為外圍計算域（外流，不長 BL）|
| Domain: wall (internal, BL in) | 此封閉幾何為域壁面，BL 往內長（內流）|

**Domain Source** 下拉可選 `Rectangle box`（顯示 X/Y Min/Max 矩形範圍）或 `Custom geometry`（隱藏矩形，改由清單中設為 Domain 角色的幾何當外框）。

**多物體 / 環狀域**：把每個形狀畫成**獨立的 PreProcessor session**、各自 Save & Export，再於 Mesh Generator 按 `Add All` 一次全部加入，逐一指定 Role 後生成。環狀域 = 外壁設 `Domain: wall`、內島設 `Boundary`。

## 完整流程管線 (Full Pipeline：CAD → 網格 → 求解 → 結果)

可用**單一 JSON 腳本**把整條流程（CAD 重採樣 → 網格生成 → UNICONES 求解 → 結果 contour）串成一鍵工作流。GUI 與 headless CLI **共用同一份腳本與階段邏輯**，不會分岔。

**GUI 一鍵：** PreProcessor GUI 右上角的 **▶ Run All** 按鈕（所有模式皆可見），對作用中的幾何依序跑完 CAD→網格→求解，並自動切到 Results 分頁顯示 contour。**Pipeline** 選單另提供 Run / Load / Save Pipeline Script。

**Headless（無視窗、輸出 PNG）：**

```bash
./run_pipeline.sh config/pipeline/template.json            # → results/pipeline/<name>_M.png
./run_pipeline.sh config/pipeline/template.json --no-solver    # 只跑到網格
```

也可讓 GUI 啟動時直接載入並自動執行某個腳本：

```bash
python3 tools/PreProcessor/gui/main.py --pipeline config/pipeline/my_case.json --run
```

**腳本格式**：一個 JSON，分成 `cad` / `mesh` / `solver` / `results` 四段，各段對應既有的設定模型（`ProjectModel` / `MeshConfig` / `SolverConfig`）。複製 `config/pipeline/template.json` 起手，改幾個數字（Mach、攻角、雷諾數、迭代次數、BC…）即可重跑。逐欄說明見 [config/pipeline/README.md](config/pipeline/README.md)。

```json
{
  "cad":    { "input_file": "examples/geometries/naca0012.dat", "skip": true },
  "mesh":   { "domain_x_min": -4, "domain_x_max": 8, "bl_layers": 15, "bc_geom": "wall" },
  "solver": { "preset": "Laminar NS (subsonic, steady)", "fs_mach": 0.3,
              "fs_flow_angle": 4.0, "fs_unit_re": 1000, "num_half_iter": 2000 },
  "results":{ "variable": "M", "save_png": "results/pipeline/case_M.png" }
}
```

> `run_pipeline.sh` 會先設定 Gmsh 的 `DYLD_LIBRARY_PATH`（同 `run.sh`）。求解器結果檔輸出到 `results/solver/<case_name>/work/`，contour PNG 到 `results/pipeline/`。注意 `print_sol_per_niter` 需 ≤ `num_half_iter`，否則求解器不會寫出結果檔。

## 近期修正 (Bug Fixes)

以下修正來自一次跨 C++ 核心與 PreProcessor GUI 的程式碼審查：

- **管線 stdout/stderr 死鎖**：`pipeline_runner._stream` 原本先讀完 stdout 再讀 stderr，當某階段在結束前對 stderr 寫入超過 OS pipe buffer（約 64 KB）時會永久卡死；改為以背景執行緒同時排空兩條管道。
- **Windows log 檔名非法字元**：`Logger.hpp` 每次執行的 log 檔名含 `:`（`%H:%M:%S`），在 Windows 為非法檔名字元、永遠開不了檔；新增無冒號的 `utcTimestampFile()` 供檔名使用，log 行前綴仍保留可讀的 ISO 時間。
- **結果欄位被衍生量遮蔽**：`TecplotResult.get_cell_field` 原本先判斷衍生量（`s`/`p0`/`T0`/`Cp`），使檔案自帶的同名原始欄位被重算值蓋掉；改為原始欄位優先，找不到才計算衍生量。
- **暫時性 weld 可能永久化**：`backend_ctrl._write_temp_config` 對 `pm.segments`/路徑的暫時性修改，其還原未放進 `finally`；中途任何例外會讓 weld 過的座標永久寫入。已改為 try/finally 保證還原。
- **Join Edges 中段種子無法連接**：`curve_ctrl._chain_edges` 只從種子邊的一端單向延伸，若最低索引的選取邊落在開放鏈中段，合法的鏈會被誤判為不連通；改為從頭尾雙向延伸。
- **Join 後未選邊設定遺失**：合併離散 (file) 邊並移除點、重新編號後，存活的未選 file 邊仍持有舊索引，導致 `update_file_segments_from_indices` 依 `(start, end)` 找不到而還原成預設值（BC/spacing 遺失）；已一併重映射存活邊的索引。
- **清理**：移除死碼 `fit_stl3d_view`；兩處內聯的 `is_closed → closed_mode` 映射改用既有的 `_legacy_closed_mode()`；`BoundaryLayer` 每節點的 `getenv` 除錯查詢改為每次 `generate()` 快取一次；合併幾乎重複的 `circle`/`arc` 取樣分支。

## 授權

MIT License

