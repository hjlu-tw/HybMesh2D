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
- **多格式輸出**：支援匯出 `.vtk` (ParaView) 與 STAR-CD (`.vrt`, `.cel`, `.bnd`) 格式。

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

### 6. 輸出與進階功能 (I/O & Advanced)

| 參數名稱 | 說明 | 預設值 |
| :--- | :--- | :--- |
| `EXPORT_VTK` | 是否預設輸出 VTK 格式 (0/1) | 1 |
| `EXPORT_STARCD` | 是否預設輸出 STAR-CD 格式 (0/1) | 0 |
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
   - `.bnd`: 邊界條件定義，包含設定的 BC 名稱。

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

