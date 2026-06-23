# HybMesh2D

HybMesh2D 是一個用於生成 2D 混合網格（Hybrid Mesh）的 C++ 工具。它能夠在幾何邊界周圍生成高品質的邊界層（四邊形網格），並在遠場自動填補非結構化（三角形網格）。

## 核心功能

- **邊界層生成**：根據給定的幾何形狀（如 NACA0012 翼型），向外生長指定層數與增長率的四邊形邊界層網格。
- **多幾何支援**：支援同時輸入多個不相交的幾何形狀，並分別生成邊界層。
- **混合網格架構**：結合近場的結構化特性（邊界層）與遠場的非結構化彈性（三角形）。
- **扇形網格 (Fan Elements)**：在幾何尖角處自動生成扇形網格以維持網格品質。
- **凹角處理與平滑**：提供凹角合併與拉普拉斯平滑技術，處理複雜幾何的網格交叉問題。
- **安全性檢查**：自動偵測幾何是否相互重疊或超出計算域邊界。
- **Gmsh 整合**：利用 Gmsh SDK 進行穩健的遠場三角化處理。
- **多格式輸出**：支援匯出 `.vtk` (ParaView)、STAR-CD (`.vrt`, `.cel`, `.bnd`)，以及 **CGNS** (`.cgns`，非結構化區 + 每 BC patch) 格式。
- **幾何關聯 (Geometry Association)**：前處理器在重採樣 `.dat` 旁產生 `.meta` sidecar，無損攜帶每點的來源段 (`seg_id`)、結構角點 (`is_corner`)、每段邊界條件 (`bc`) 與曲線型別 (`curve_kind`)。詳見下方「幾何 metadata sidecar」。
- **解析邊界層法向**：在 line/circle 表面以精確解析法向生長邊界層 (取代有限差分)，對曲面 (圓柱、前緣) 更準確。可由 `BL_USE_ANALYTIC_GEOM` 開關，預設關閉。
- **每段邊界條件**：可在 GUI CAD 檢視器逐段指定 BC，透過 sidecar 帶到 mesher，取代全域 `BC_GEOM` 的位置反推。

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
- `-geom <path1> [path2]...`: 指定一個或多個幾何資料檔。
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
| `DOMAIN_X_MIN` / `MAX` | 計算域 X 軸範圍 | -10.0 / 10.0 |
| `DOMAIN_Y_MIN` / `MAX` | 計算域 Y 軸範圍 | -10.0 / 10.0 |
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

## 授權

MIT License

