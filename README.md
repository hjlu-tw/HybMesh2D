# HybMesh2D

HybMesh2D 是一個用於生成 2D 混合網格（Hybrid Mesh）的 C++ 工具。它能夠在幾何邊界周圍生成高品質的邊界層（四邊形網格），並在遠場自動填補非結構化（三角形網格）。

## 核心功能

- **邊界層生成**：根據給定的幾何形狀（如 NACA0012 翼型），向外生長指定層數與增長率的四邊形邊界層網格。
- **混合網格架構**：結合近場的結構化特性（邊界層）與遠場的非結構化彈性（三角形）。
- **幾何相交檢查**：自動偵測輸入幾何是否超出計算域邊界，確保網格生成的正確性。
- **Gmsh 整合**：利用 Gmsh SDK 進行穩健的遠場三角化處理。
- **VTK 輸出**：支援匯出 `.vtk` 格式，可直接在 ParaView 中進行視覺化。

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
