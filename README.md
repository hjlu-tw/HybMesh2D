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
- **批次佇列 (Batch Queue)**：一次排入多個 pipeline 腳本連續執行，GUI 與 CLI 共用同一個 runner；GUI 的 Cancel 會**中止正在跑的那個 case**（不只停下佇列）。詳見下方「批次佇列」。
- **長度單位 (Length Units)**：模型宣告單一長度單位（m/cm/mm/µm/in/ft/自訂）。這不是裝飾——求解器是有量綱的，`Linf` 由單位推導而非手填，並在 Solver 面板即時顯示參考雷諾數。詳見下方「長度單位與參考雷諾數」。

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
| `FARFIELD_GROWTH_RATE` | 由表面往遠場的尺寸增長率。**無邊界層時同樣生效**（改由幾何表面出發成長，先前僅在有 BL 外緣時作用，無 BL 則整域為均勻遠場尺寸）。 | 0.1 |

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
| `BL_FRONT_SMOOTHING_ITERS` | 每層對推進前緣做切向平滑的迭代次數（僅平滑一般節點，保留角點/扇形/交界；投影掉法向分量故層高不變）。0=關閉（預設，維持既有網格）；用於抑制非均勻輸入在外層殘留的漂移。 | 0 |

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
| `LENGTH_UNIT` | 模型座標的長度單位（`m`/`cm`/`mm`/`um`/`in`/`ft`/`custom`）。mesher **只記錄不換算**（它只拿長度彼此相比），會印在 banner 並寫進 provenance sidecar | m |
| `LENGTH_UNIT_METRES` | `LENGTH_UNIT custom` 時，一個模型單位等於幾公尺 | 1.0 |
| `LENGTH_UNIT_NAME` | 自訂單位的顯示名稱 | (空) |

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

1. **VTK 格式**: 生成 `results/meshes/<case>/mesh_<case>.vtk`，建議使用 [ParaView](https://www.paraview.org/) 檢視。
2. **STAR-CD 格式**: 生成一組三個檔案：
   - `.vrt`: 節點座標。
   - `.cel`: 單元（包含三角形與四邊形）定義。
   - `.bnd`: 邊界條件定義，包含設定的 BC 名稱（幾何邊優先採用 sidecar 的每段 `bc`，否則退回 `BC_GEOM`）。
3. **CGNS 格式** (選用): 生成 `*.cgns`（非結構化單一區，含三角/四邊單元 section 與每個 BC 一組 BAR_2 edge section + `BC_t` patch；BCType 對應 wall/inlet/outlet 等）。適合無損交給支援 CGNS 的求解器。可用 `cgnscheck` 驗證。

## 輸出目錄結構與清理 (`results/`)

所有產物都寫在 `results/`（整個目錄已被 `.gitignore` 排除，不進版控），並依用途分子目錄。網格輸出採 **per-case** 佈局：每個案例自成一夾,頂層不再堆積散檔。

| 子目錄 | 內容 | 可否重生 |
|--------|------|----------|
| `results/meshes/<case>/` | 網格輸出 `mesh_<case>.{vtk,vrt,cel,bnd,cgns}` 與 `.provenance.json` | ✅ 可重跑重生 |
| `results/solver/<case>/` | 求解器 case 目錄（`work/`、`grid/`、`dll/`）；`work/binDumpZ.dat.*` 為 restart 續跑用 | ✅ 可重跑（刪 `binDumpZ` 會失去 restart） |
| `results/resampled/` | 表面重採樣輸出 `.dat` + `.meta` | ✅ 由 CAD 來源重生 |
| `results/inputs/` | CAD 來源幾何 `.dat` | ⚠️ 來源檔,建議保留 |
| `results/logs/`、`results/pipeline/` | 執行紀錄、pipeline 腳本 | — |

`<case>` 由邊界幾何檔名推導（單一→其 stem，多個→各 stem 串接，無幾何→`cartesian`）；此規則由 `MeshConfig.auto_output_name()`（GUI）與 `src/main.cpp` 預設（CLI）共用。

**定期清理**：`results/` 只會隨著跑不同案例慢慢變大（重跑同一 case 是覆蓋、不增量）。需要釋放空間時用清理腳本（預設 dry-run,加 `--force` 才實際刪除,一律保留 `inputs/`）：

```bash
./tools/scripts/clean_results.sh            # 列出會刪什麼、釋放多少（不刪）
./tools/scripts/clean_results.sh --force    # 實際刪除可重生產物
```

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

## 批次佇列 (Batch Queue)

同一份 runner 可依序跑多個 pipeline 腳本（`.json` 或 `.hws` 工作區皆可）。

**Headless：**

```bash
./run_batch.sh case_a.json case_b.hws --no-solver
./run_batch.sh @manifest.txt            # 清單檔，一行一個路徑
```

**GUI：Pipeline ▸ Batch Queue…**（modeless 對話框，關掉主視窗以外的操作不會清空已排好的佇列），提供逐案狀態表：

- **Cancel 會中止正在執行的那個 case**，不是等它跑完才停。`should_stop()` 只在 case 之間輪詢，這對「不留下寫到一半的輸出目錄」是對的，但單靠它按下 Cancel 後可能數分鐘到數小時毫無反應；因此 `pipeline_runner` 另外把每個階段的子行程往上交（`on_process`），worker 以 SIGTERM → 寬限 → SIGKILL 對整個 process group 中止（階段是一棵行程樹：mpirun ranks、gmsh helper，只殺直接子行程會留下孤兒）。兩個機制缺一不可：一個停下手上的工作，一個阻止佇列開始下一個 case。
- **案例名稱衝突在「排入佇列時」就提示**，不是等到執行。輸出路徑由 case 名稱推導，同名等於一個 case 默默覆蓋另一個的網格。
- 讀不到的腳本會顯示為帶原因的跳過列 —— 安靜地跑完 10 個裡的 9 個，比明確失敗更糟。

## 長度單位與參考雷諾數 (Length Units)

模型宣告**單一**長度單位（Mesh 面板最上一列，或設定檔的 `LENGTH_UNIT`）：`m` / `cm` / `mm` / `µm` / `in` / `ft` / 自訂。

這不是顯示用的標籤——**求解器是有量綱的**。依 UNICONES 手冊，`fs_UnitRe` 是「每公尺」的單位雷諾數、`Linf` 是「每個網格單位等於幾公尺」（手冊自己的範例即用 `Linf 0.0254` 表示英吋網格），所以

```
Re = fs_UnitRe × Linf
```

一個以 mm 建立、卻把 `Linf` 留在 1 的網格，會用**1000 倍**的雷諾數去跑一個外觀完全正常的網格。

規則：

- **`Linf` 由宣告的單位推導，不是手打的。** 舊有、手動設過 `linf` 又沒有 `length_unit` 的設定檔，載入時會關掉推導以保住原本的雷諾數；`unit_check()` 則會指出這個 `linf` 實際隱含的是哪個單位。
- **改單位只是改標示，永遠不換算數值。** 只有兩處會真的換算：`Linf`，以及**匯入時**的座標（匯入單位對話框，每次匯入問一次，預設不換算，headless 時靜默且不動作）。
- **單位顯示在 spin box 自己的 suffix 上**，不寫進標籤文字——後綴跟著擁有該數值的元件走，不會被忘記。只有物理長度有單位；增長率、角度、計數沒有。
- 對「看似合理但其實錯誤」的單位，真正的防線是 Solver 面板的**參考雷諾數即時讀數**，以及 `run_pipeline.py` 的 `[INFO] reference Reynolds number` 那一行。尺寸合理性檢查只抓得到嚴重錯誤，它也如此聲明。
- Mesher **只記錄、不換算** `LENGTH_UNIT`（它只拿長度彼此相比），會印在 banner，因此也會落進 provenance sidecar。

## PreProcessor GUI 使用性

- **CAD 畫布工具（CAD 工具列）**
  - **Measure**：兩次點擊量一段距離，讀出 `d / dx / dy / angle`（四行、等寬字型、深色底板，貼在被量線段上）。
  - **Snap**：格點吸附 + 可調步長。
  - **◀ / ▶**：畫布視角的上一步 / 下一步（縮放與平移的歷史，像瀏覽器的上下頁）。一次滾輪縮放或拖曳平移記作**一筆**歷史。
  - 這些工具互斥：啟用其中一個會自動離開另外兩個（含 weld 工具），工具列的切換按鈕跟著畫布狀態走。
- **狀態列**：常駐顯示目前階段 / 選取狀態 / 進行中的工作。
- **Geometry Statistics（CAD 側欄，預設收合）**：點數、開/封閉、bbox、周長、點距 min/mean/max，以及**均勻度**——相鄰間距的最大擴張比、超過閾值的數量與**位置**。相鄰間距跳動超過約 1.2× 的幾何會長出品質不良的邊界層，過去只能等生成網格失敗才發現。
- **來源檔變更偵測**：工作區會連同幾何點座標一起記錄來源檔的指紋（size + mtime + SHA-256）。若 `.dat`/`.stl` 在存檔後被 CAD 重新匯出、被腳本重新產生或手動編輯，重新開啟時會明確告知——否則畫布顯示的是存檔當時的點，而網格階段是重新讀檔，等於對使用者從未看過的幾何生成網格。
- **By End Spacing**：`tanh` 與 `geometric` 兩種分佈策略可直接指定端點間距（第一格尺寸），不必再用抽象的 intensity / 增長比去猜。（`tanh` 的間距求解改為 bisection `solveTanhDelta()`，舊的啟發式對應實測差約 40 倍，且必須兩端都設定才會生效。）
- **介面語言**：**Help ▸ Language**（English / 繁體中文），下次啟動生效。目前完整翻譯的是常駐介面（選單列 + 狀態列）；面板欄位、對話框內文與日誌訊息仍為英文。

## 近期修正 (Bug Fixes)

以下修正來自 2026-08 的 GUI 使用回報與後續驗證：

- **CAD 工具列文字被截斷**：排版靠 `threshold = 1200` 決定單排或雙排，而這行有兩個錯誤——它比的是**視窗**寬度，但工具列比視窗窄（側欄佔掉其餘空間，1600px 視窗只留 1240px 工具列）；而且硬編數字在新增、改名或翻譯任何控制項後就過期（中文標籤不等於英文寬度）。改為 `_row_width()` 以各元件自己的 sizeHint 加上間距與邊界實際量測，兩個門檻值皆移除。已知限制：視窗小於約 900px 時兩排仍會溢出，需要可水平捲動的工具列（另案）。
- **snap 控制項變成兩個浮動視窗**：`grid_snap_cb` 與 `grid_snap_step` 建立時沒有 parent，而在 Qt 中無 parent 的 QWidget 就是**頂層視窗**——因此出現兩個關不掉、也不隨主視窗結束的浮動面板；另外三個畫布工具則從未被加進工具列的排版清單，等於隱形。兩種失效都是無聲的。已補上 parent 與兩種排版的清單，並加上針對此類錯誤的檢查（主視窗必須是唯一可見的頂層元件；`*_tb_widgets` 中每個元件都必須被排版或明確隱藏）。
- **視角上一步只退了一根頭髮**：`ViewHistory` 的容差 `1e-9` 只合併位元完全相同的視角，但 pyqtgraph 的 `sigRangeChanged` 是**每軸各發一次**，一次 `setRange` 就推入兩筆僅差毫釐的紀錄，按一次 ◀ 只是回到你正在看的那一格。改為：容差取 span 的 1%（尺度無關，在單位可變之後更重要），並以 350 ms 靜止後才記錄，使一次滾輪縮放或拖曳平移成為一筆歷史。
- **量測工具與繪製工具互搶點擊**：互斥原本寫在各個 `start_*` 內兩兩處理，三個工具有六個方向卻只實作三個——Measure 會停掉另外兩個，但啟動 Polygon/Line 或 weld **不會**停掉 Measure。由於 measure 比繪製更早攔截點擊，Measure 開著時畫 Polygon 只會不斷量距離、一個點都放不下去。改為單一 `EXCLUSIVE_TOOLS` 表，六個方向由結構保證對稱，並讓工具列按鈕跟隨畫布狀態彈起。
- **量測讀數與幾何難以分辨**：畫布上已有約 25 種顏色，舊的琥珀色 `#f5c542` 與自動封閉邊 `#FFD700`、作用中線段 `#FFB347` 及兩個 session 色的最小 CIELAB ΔE 只有 **6.1**（一眼看去同色）；純白更糟，ΔE 為 **0**，因為白圈正是端點標記。改用最小 ΔE 達 **64** 的 `#DD11FF`，並加上其他項目都沒有的深色底板，讓它在顏色被辨識之前就先讀作「標籤」而非幾何。
- **階段設定的模型落後於面板**：`global_*_config` 只在該階段真的執行時才更新，於是出現四份各自不完整的補救複製（兩種欄位不同的部分複製、solver 完全沒同步、工作區存檔直接序列化面板）。同一個數值有四個真相來源，各自只在某個時刻是對的。改為單向資料流：**面板編輯 → 同步到模型**，模型才是真相；面板不擁有的欄位（`PRESERVED_FIELDS`）由 AST 從面板自身原始碼推導並在建置時把關，因此新增一個沒有對應元件的模型欄位會讓建置失敗，而不是默默失效或被清空。順帶修掉一個既有的資料遺失：工作區存檔會把未擁有的欄位寫成 dataclass 預設值（`bc_geom = symmetry` 被存成 `wall`）。

以下修正來自一次跨 C++ 核心與 PreProcessor GUI 的程式碼審查：

- **管線 stdout/stderr 死鎖**：`pipeline_runner._stream` 原本先讀完 stdout 再讀 stderr，當某階段在結束前對 stderr 寫入超過 OS pipe buffer（約 64 KB）時會永久卡死；改為以背景執行緒同時排空兩條管道。
- **Windows log 檔名非法字元**：`Logger.hpp` 每次執行的 log 檔名含 `:`（`%H:%M:%S`），在 Windows 為非法檔名字元、永遠開不了檔；新增無冒號的 `utcTimestampFile()` 供檔名使用，log 行前綴仍保留可讀的 ISO 時間。
- **結果欄位被衍生量遮蔽**：`TecplotResult.get_cell_field` 原本先判斷衍生量（`s`/`p0`/`T0`/`Cp`），使檔案自帶的同名原始欄位被重算值蓋掉；改為原始欄位優先，找不到才計算衍生量。
- **暫時性 weld 可能永久化**：`backend_ctrl._write_temp_config` 對 `pm.segments`/路徑的暫時性修改，其還原未放進 `finally`；中途任何例外會讓 weld 過的座標永久寫入。已改為 try/finally 保證還原。
- **Join Edges 中段種子無法連接**：`curve_ctrl._chain_edges` 只從種子邊的一端單向延伸，若最低索引的選取邊落在開放鏈中段，合法的鏈會被誤判為不連通；改為從頭尾雙向延伸。
- **Join 後未選邊設定遺失**：合併離散 (file) 邊並移除點、重新編號後，存活的未選 file 邊仍持有舊索引，導致 `update_file_segments_from_indices` 依 `(start, end)` 找不到而還原成預設值（BC/spacing 遺失）；已一併重映射存活邊的索引。
- **清理**：移除死碼 `fit_stl3d_view`；兩處內聯的 `is_closed → closed_mode` 映射改用既有的 `_legacy_closed_mode()`；`BoundaryLayer` 每節點的 `getenv` 除錯查詢改為每次 `generate()` 快取一次；合併幾乎重複的 `circle`/`arc` 取樣分支。

以下修正來自 2026-07 的八項使用回報（C++ 核心 + GUI）：

- **圓柱/圓弧 BL 外層歪斜、內流自交**：封閉迴圈的接縫起點被 resampler 標成 corner，這個近乎直線（≈181°）的「假角點」觸發 method-5 混合，其影響範圍在小迴圈上會繞完整個周長、把所有 column 拉向接縫頂點，使乾淨圓柱長成歪斜淚滴狀。修正：以 `nearStraightInit`（|外角−180°|<8°）將假角點排除於步長修正與混合之外，並去除重合的首尾接縫節點。圓柱 gr1.2/L20 現為乾淨同心圓環，naca0012 不受影響。
- **遠場增長率在無邊界層時失效**：`Mesh.cpp` 新增 `surfaceLineTags`（兩端 `geomId≥0` 的表面邊），無 BL 時改由表面出發套用 `FARFIELD_GROWTH_RATE`（並可選 `BL_FRONT_SMOOTHING_ITERS` 前緣平滑，見上表）。
- **STAR-CD/VTK 匯出未依指定檔名**：匯出改為優先讀取 Output 欄位的即時值，而非生成當下鎖定的舊設定（「生成後才改名」曾被忽略）。
- **Mesh Generator 左欄數值會跳回舊值**：數值 spinbox 的編輯從未寫回 `global_mesh_config`，故新增/移除/切換幾何（會重新套用設定）時被蓋回；改在每次 layer 操作前把面板即時 scalar 併回（保留 geometry/roles/BC）。左欄並加上超出寬度時可左右捲動的水平捲軸。
- **IBM phi 勾選後看不到**：phi 散點顏色太暗且被不透明 STL 面遮住；提亮 fluid 顏色/加大點徑，並以關閉深度測試的 GL 設定讓 phi 畫在 STL 之上；`n_solid==0` 時額外印出 domain 邊界框協助診斷。
- **跳出視窗掉到最底層**：`keep_on_top()` 將 `Qt.Tool` 彈窗重新 parent 到頂層主視窗，使 modeless 對話框穩定浮在主視窗之上（但不蓋其他 app）。
- **Weld 改為拖曳式**：weld 工具改為在每個端點顯示可拖曳握把，拖到目標點即自動 snap 黏合（拖到空白處則移動該端點），取代原本的點兩下流程。

## 授權

MIT License

