# HybMesh2D

HybMesh2D 是一個用於生成 2D 混合網格（Hybrid Mesh）的 C++ 工具。它能夠在幾何邊界周圍生成高品質的邊界層（四邊形網格），並在遠場自動填補非結構化（三角形網格）。

## 核心功能

- **邊界層生成**：根據給定的幾何形狀（如 NACA0012 翼型），向外生長指定層數與增長率的四邊形邊界層網格。
- **混合網格架構**：結合近場的結構化特性（邊界層）與遠場的非結構化彈性（三角形）。
- **幾何相交檢查**：自動偵測輸入幾何是否超出計算域邊界，確保網格生成的正確性。
- **Gmsh 整合**：利用 Gmsh SDK 進行穩健的遠場三角化處理。
- **VTK 輸出**：支援匯出 `.vtk` 格式，可直接在 ParaView 中進行視覺化。

## 網格架構與過渡機制

HybMesh2D 將整個計算域劃分為三個主要概念區域，並實現了平滑的尺寸過渡：

1. **幾何邊界 (Geometry Boundary)**
   - 使用者輸入的幾何形狀（如翼型）。在外部流場計算中，內部通常視為不生成網格的「洞」，網格生成的起點即為此邊界。

2. **邊界層區域 (Boundary Layer Region)**
   - 緊貼幾何邊界向外生長的結構化區域，由**四邊形 (Quadrilaterals)** 組成。
   - 專門用於捕捉流體力學中的邊界層效應（如高速度梯度）。透過設定檔嚴格控制第一層高度、增長率與總層數。

3. **遠場與過渡區域 (Far-field & Transition Region)**
   - 從邊界層最外圈延伸至計算域外部邊界的空間，由 Gmsh 生成的**三角形 (Triangles)** 組成（非結構化網格）。
   - **過渡機制**：程式會將邊界層最外層的四邊形高度（`lastH`）擷取出來，並傳遞給 Gmsh。Gmsh 會以此作為起始網格尺寸，向外平滑放大三角形，直到達到設定的遠場最大網格尺寸（`farFieldSize`）。這種設計完美兼顧了過渡層的功能，確保結構化與非結構化網格交界處不會出現長寬比的突變。

## 檔案結構

- `src/`: 原始程式碼 (`main.cpp`, `Mesh.cpp`, `BoundaryLayer.cpp`)。
- `include/`: 標頭檔，定義資料結構與算法介面。
- `geometries/`: 存放邊界幾何資料（如 `.dat` 點位檔）。
- `config/`: 存放參數設定檔 (`Background_para.dat`)。
- `results/`: 網格生成後的輸出路徑。

## 系統需求

- **編譯器**: 支援 C++17 的編譯器 (如 GCC, Clang, MSVC)。
- **建置工具**: CMake 3.10+。
- **外部依賴**: [Gmsh SDK](https://gmsh.info/) (需於 `CMakeLists.txt` 中配置正確的路徑)。

## 編譯方式

```bash
mkdir build
cd build
cmake ..
make
```

## 執行方式

預設執行方式（使用 `config/Background_para.dat` 中的設定）：

```bash
./HybMesh2D
```

自定義參數執行：

```bash
./HybMesh2D -conf config/custom_para.dat -geom geometries/naca0012.dat
```

### 命令列參數

- `-conf <path>`: 指定背景參數設定檔路徑。
- `-geom <path>`: 指定幾何形狀資料檔路徑。

## 視覺化

生成的網格會存放在 `results/output.vtk`。建議使用 [ParaView](https://www.paraview.org/) 開啟並檢視結果。

## 授權

[請在此加入您的授權資訊]
