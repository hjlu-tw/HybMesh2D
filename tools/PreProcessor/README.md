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

## 範例檔案
- `config/comprehensive_example.json`: 基礎功能綜合展示。
- `config/industrial_pro_example.json`: 專業翼型布點與品質監控展示。
- `config/multi_element_example.json`: 多物體並行處理展示。
