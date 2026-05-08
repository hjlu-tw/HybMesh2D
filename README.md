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

執行快速編譯腳本：

```bash
./build.sh
```

這會將執行檔輸出至 `build/HybMesh2D`。

## 執行方式

```bash
./HybMesh2D [options]
```

### 常用命令列參數

- `-conf <path>`: 指定背景參數設定檔路徑（預設: `config/Background_para.dat`）。
- `-geom <path1> [path2]...`: 指定一個或多個幾何資料檔。
- `-out_vtk <0|1>`: 是否輸出 VTK 檔案 (1: 開啟, 0: 關閉)。
- `-out_starcd <0|1>`: 是否輸出 STAR-CD 檔案。
- `-bc_xmin <name>`: 指定 STAR-CD X-min 邊界的名稱（例如 inlet）。
- `-bc_xmax <name>`: 指定 STAR-CD X-max 邊界的名稱（例如 outlet）。
- `-bc_geom <name>`: 指定幾何表面的邊界名稱（例如 wall）。

## 設定檔參數說明 (`Background_para.dat`)

| 參數名稱 | 說明 | 預設值 |
| :--- | :--- | :--- |
| `DOMAIN_X_MIN` / `MAX` | 計算域 X 軸範圍 | -10.0 / 10.0 |
| `DOMAIN_Y_MIN` / `MAX` | 計算域 Y 軸範圍 | -10.0 / 10.0 |
| `BL_INITIAL_THICKNESS` | 邊界層第一層高度 | 0.01 |
| `BL_GROWTH_RATE` | 邊界層增長率 | 1.2 |
| `BL_LAYERS` | 邊界層總層數 | 5 |
| `BL_FAN_NODES` | 尖角處扇形分割數量 | 5 |
| `BL_FAN_ANGLE_THRESHOLD`| 觸發扇形網格的轉角閾值 (度) | 60.0 |
| `BL_SMOOTHING_ITERS` | 邊界層生成後的平滑迭代次數 | 0 |
| `BL_MERGE_CONCAVE` | 是否合併凹角處的擠壓節點 (0/1) | 0 |
| `FARFIELD_MESH_SIZE` | 遠場最大網格尺寸 | 1.0 |
| `FARFIELD_GROWTH_RATE` | 從邊界層到遠場的尺寸增長率 | 0.1 |
| `EXPORT_STARCD` | 是否預設輸出 STAR-CD 格式 (0/1) | 0 |

### 進階參數 (Advanced Parameters)

| 參數名稱 | 說明 | 預設值 |
| :--- | :--- | :--- |
| `SURFACE_MESH_SIZE` | 表面初始網格尺寸 | 0.1 |
| `BL_AUTO_FAN_NODES` | 是否自動計算尖角扇形數量 (0: 關閉, 1: 全域平均, 2: 局部平均) | 0 |
| `BL_CONCAVE_METHOD` | 凹角處理方法 (0: 合併, 5: 厚度混合) | 0 |
| `BL_TRANSITION_LAYERS` | 從邊界層到遠場的過渡層數 | 3 |
| `BL_AUTO_TRANSITION_LAYERS` | 是否自動計算過渡層數 | 0 |
| `GMSH_ALGORITHM` | Gmsh 網格生成演算法 (預設 6: Frontal-Delaunay) | 6 |
| `GMSH_OPTIMIZE` | 是否開啟 Gmsh 網格優化 | 1 |
| `BC_XMIN` / `XMAX` / `YMIN` / `YMAX` | STAR-CD 邊界名稱設定 | wall |
| `BC_GEOM` | STAR-CD 幾何表面邊界名稱 | wall |
| `EXPORT_VTK` | 是否預設輸出 VTK 格式 | 1 |

## 視覺化與輸出

1. **VTK 格式**: 生成 `results/*.vtk`，建議使用 [ParaView](https://www.paraview.org/) 檢視。
2. **STAR-CD 格式**: 生成一組三個檔案：
   - `.vrt`: 節點座標。
   - `.cel`: 單元（包含三角形與四邊形）定義。
   - `.bnd`: 邊界條件定義，包含設定的 BC 名稱。

## 授權

[請在此加入您的授權資訊]
