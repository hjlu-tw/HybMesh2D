# Surface Resampler (PreProcessor)

這是一個用於對 2D 幾何邊界（`.dat` 檔案）進行重新布點（Resampling）的工具。在生成混合網格之前，良好的表面網格分佈對於邊界層的品質至關重要。

## 工具組成

1.  **Python GUI (`gui/main.py`)**: 
    - 提供視覺化界面，讓使用者點選幾何上的關鍵點來劃分分段（Segments）。
    - 根據使用者輸入的點數，自動生成 `.json` 設定檔。
2.  **C++ 核心 (`surface_resampler`)**:
    - 高效地執行實際的插值與重採樣運算。
    - 支援分段處理，確保幾何特徵（如尖角）在重採樣後得以保留。

## 編譯方式

請在專案根目錄使用 CMake 進行編譯：

```bash
mkdir build
cd build
cmake ..
make
```

編譯後會產生 `build/surface_resampler` 執行檔。

## JSON 設定檔格式說明

設定檔定義了輸入輸出路徑以及各分段的重採樣策略。範例如下：

```json
{
  "input_file": "path/to/input.dat",
  "output_file": "path/to/output.dat",
  "segments": [
    {
      "id": 1,
      "start_index": 0,
      "end_index": 50,
      "strategy": "uniform",
      "parameters": {
        "n_points": 100
      }
    },
    {
      "id": 2,
      "start_index": 50,
      "end_index": -1,
      "strategy": "uniform",
      "parameters": {
        "n_points": 50
      }
    }
  ]
}
```

### 參數詳解

- **`input_file`**: 原始幾何檔案路徑。
- **`output_file`**: 重採樣後的幾何檔案輸出路徑。
- **`segments`**: 一個陣列，定義幾何的不同區段。
    - **`type`**: 區段類型。
        - `file` (預設): 從 `input_file` 中擷取點。需提供 `start_index` 與 `end_index`。
        - `curve`: 根據數學公式產生點。
    - **`formula`** (僅限 `type`: `curve`):
        - 可使用預設關鍵字：`sin`, `polynomial`, `line`。
        - **支援自定義公式字串**：例如 `"x^3 - 2*x"` 或 `"sin(x) + cos(2*x)"`。
        - 支援運算子：`+`, `-`, `*`, `/`, `^` (次方), `()` (括號)。
        - 支援函數：`sin`, `cos`, `tan`, `exp`, `log`, `sqrt`, `abs`。
    - **`parameters`**:
        - `range` (僅限 `curve`): `[x_start, x_end]` 定義公式的 X 軸範圍。
        - `n_points`: 該線段重採樣後的目標點數（固定數量模式）。
        - `spacing`: 該線段重採樣後的目標格點間距（固定寬度模式）。**優先級高於 `n_points`**。
        - `sensitivity` (僅限 `curvature` 策略): 對曲率的敏感度（預設 1.0）。
        - `ratio` (僅限 `geometric` 策略): 相鄰間距的增長倍率（預設 1.1）。
        - `intensity` (僅限 `tanh` 策略): 雙端加密強度（預設 2.0）。
    - **`strategy`**: 重採樣策略。
        - `uniform` (預設): 均勻分佈。
        - `curvature`: 自動在曲率較大處加密。
        - `cosine`: 雙端加密。
        - `geometric`: 幾幾何級數分布（等比間距）。
        - `tanh`: 雙曲線正切分布（平滑雙端加密）。

## 使用流程

### 步驟 1：使用 GUI 定義分段

執行 Python 腳本並傳入幾何檔案：

```bash
python tools/PreProcessor/gui/main.py examples/geometries/circle.dat
```

- **左鍵點擊**: 選取或移除分段點（會自動吸附到最近的節點）。
- **Enter**: 確認分段並輸入每個分段所需的點數。
- 結束後會生成 `gui_config.json` 並自動嘗試調用 C++ 核心。

### 步驟 2：執行 C++ 重採樣 (手動)

如果你已經有了 `.json` 設定檔，可以直接執行（範例位於 `config/` 目錄）：

```bash
./build/surface_resampler tools/PreProcessor/config/test_config.json
```

生成的結果可以用 ParaView 或簡單的繪圖工具查看。

### 步驟 3：視覺化結果 (選用)

你可以使用提供的 Python 腳本快速查看 `.dat` 檔案的布點情況：

```bash
python tools/scripts/visualize_dat.py Results/circle_resampled.dat
```
