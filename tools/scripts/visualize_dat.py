#!/usr/bin/env python3
"""
Visualize 2D geometry .dat files.
Usage: python visualize_dat.py <path_to_dat_file> --config <path_to_json>
"""

import sys
import os
import matplotlib.pyplot as plt
import numpy as np
import json
import argparse

def get_seg_endpoints(seg, global_points):
    """預測線段的理論起點與終點座標"""
    seg_type = seg.get("type", "file")
    params = seg.get("parameters", {})
    rng = params.get("range", [0.0, 1.0])
    
    if seg_type == "file":
        if global_points is None: return None, None
        start_idx = seg.get("start_index", 0)
        end_idx = seg.get("end_index", 0)
        if end_idx == -1: end_idx = len(global_points) - 1
        if start_idx < len(global_points) and end_idx < len(global_points):
            return global_points[start_idx], global_points[end_idx]
        return None, None
    
    # 支援參數化 x_formula, y_formula
    if "x_formula" in seg and "y_formula" in seg:
        try:
            xf = seg["x_formula"].replace("^", "**").replace("sin", "np.sin").replace("cos", "np.cos").replace("pi", "np.pi")
            yf = seg["y_formula"].replace("^", "**").replace("sin", "np.sin").replace("cos", "np.cos").replace("pi", "np.pi")
            eval_x = lambda t: eval(xf, {"np": np, "t": t})
            eval_y = lambda t: eval(yf, {"np": np, "t": t})
            p0 = np.array([eval_x(rng[0]), eval_y(rng[0])])
            p1 = np.array([eval_x(rng[1]), eval_y(rng[1])])
            return p0, p1
        except: return None, None

    formula = seg.get("formula", "line")
    if formula == "sin":
        amp, freq, phase, off_y = params.get("amplitude", 1.0), params.get("frequency", 1.0), params.get("phase", 0.0), params.get("offset_y", 0.0)
        f = lambda x: amp * np.sin(freq * x + phase) + off_y
        return np.array([rng[0], f(rng[0])]), np.array([rng[1], f(rng[1])])
    elif formula == "polynomial":
        coeffs = params.get("coeffs", [0.0, 1.0])
        f = lambda x: sum(c * (x**i) for i, c in enumerate(coeffs))
        return np.array([rng[0], f(rng[0])]), np.array([rng[1], f(rng[1])])
    elif formula == "line":
        p0 = np.array([params.get("x0", 0.0), params.get("y0", 0.0)])
        p1 = np.array([params.get("x1", 1.0), params.get("y1", 1.0)])
        return p0, p1
    else:
        try:
            py_f = formula.replace("^", "**").replace("sin", "np.sin").replace("cos", "np.cos").replace("pi", "np.pi")
            f = lambda x: eval(py_f, {"np": np, "x": x})
            return np.array([rng[0], f(rng[0])]), np.array([rng[1], f(rng[1])])
        except: return None, None

def detect_feature_points(points, threshold_degrees):
    """與 C++ detectFeaturePoints 邏輯一致"""
    if len(points) < 3:
        return [0, len(points) - 1]
    
    features = [0]
    threshold_rad = threshold_degrees * np.pi / 180.0
    
    for i in range(1, len(points) - 1):
        v1 = points[i] - points[i-1]
        v2 = points[i+1] - points[i]
        
        l1 = np.linalg.norm(v1)
        l2 = np.linalg.norm(v2)
        if l1 < 1e-10 or l2 < 1e-10: continue
        
        dot = np.dot(v1/l1, v2/l2)
        angle = np.arccos(np.clip(dot, -1.0, 1.0))
        
        if angle > threshold_rad:
            features.append(i)
            
    features.append(len(points) - 1)
    return sorted(list(set(features)))

from matplotlib.collections import LineCollection
from matplotlib.colors import ListedColormap, BoundaryNorm

def plot_element(ax, element_config, element_id, quality_mode=False):
    """繪製單個元素及其線段"""
    output_file = element_config.get("output_file")
    if not output_file or not os.path.exists(output_file):
        return None

    try:
        points = np.loadtxt(output_file)
    except:
        return None

    if len(points) < 2: return points

    if not quality_mode:
        # --- 一般模式：按線段著色 ---
        segments = element_config.get("segments", [])
        current_idx = 0
        
        # 載入原始點
        global_points = None
        if "input_file" in element_config and os.path.exists(element_config["input_file"]):
            try:
                global_points = np.loadtxt(element_config["input_file"])
                if element_config.get("is_closed", False):
                    if np.linalg.norm(global_points[0] - global_points[-1]) > 1e-9:
                        global_points = np.vstack([global_points, global_points[0]])
            except: pass

        for i, seg in enumerate(segments):
            seg_id = seg.get("id", "?")
            seg_type = seg.get("type", "file")
            auto_split = seg.get("auto_split", False)
            split_threshold = seg.get("split_threshold", 20.0)

            # 決定子區段範圍
            sub_ranges = []
            if seg_type == "curve":
                sub_ranges.append(None)
            else:
                s_idx, e_idx = seg.get("start_index", 0), seg.get("end_index", -1)
                if e_idx == -1 and global_points is not None: e_idx = len(global_points) - 1
                
                if auto_split and global_points is not None:
                    sub_pts = global_points[s_idx : e_idx + 1]
                    local_features = detect_feature_points(sub_pts, split_threshold)
                    for f in range(len(local_features) - 1):
                        sub_ranges.append((s_idx + local_features[f], s_idx + local_features[f+1]))
                else:
                    sub_ranges.append((s_idx, e_idx))

            for sub_idx, r in enumerate(sub_ranges):
                # 計算點數
                n_points = seg.get("parameters", {}).get("n_points")
                
                # 取得該段原始點以計算長度或預設點數
                if seg_type == "file" and global_points is not None:
                    sp_raw = global_points[r[0] : r[1] + 1]
                    if n_points is None: n_points = len(sp_raw)
                    if seg.get("parameters", {}).get("spacing") is not None:
                        ds = seg["parameters"]["spacing"]
                        total_l = np.sum(np.sqrt(np.sum(np.diff(sp_raw, axis=0)**2, axis=1)))
                        n_points = int(round(total_l / ds)) + 1
                
                if n_points is None: n_points = 50
                if n_points < 2: n_points = 2

                start = current_idx
                # 如果是最後一個子段且是最後一個 Segment，取到最後
                if i == len(segments)-1 and sub_idx == len(sub_ranges)-1:
                    end = len(points)
                else:
                    end = current_idx + n_points
                
                if end > len(points): end = len(points)
                if start >= len(points): break

                seg_pts = points[start:end]
                label = f"E{element_id}-S{seg_id}"
                if len(sub_ranges) > 1: label += f"-{sub_idx+1}"
                ax.plot(seg_pts[:, 0], seg_pts[:, 1], '.-', markersize=4, label=label)
                current_idx = end - 1
    else:
        # --- 品質模式：熱向圖 ---
        diffs = np.diff(points, axis=0)
        ds = np.sqrt(np.sum(diffs**2, axis=1))
        ds[ds < 1e-12] = 1e-12
        # 計算相鄰間距比：r[i] = ds[i] / ds[i-1] (反應點 i 的擴張程度)
        ratios = np.ones(len(points))
        ratios[1:-1] = ds[1:] / ds[:-1]
        
        # 建立線段集合
        pts_reshaped = points.reshape(-1, 1, 2)
        segments_list = np.concatenate([pts_reshaped[:-1], pts_reshaped[1:]], axis=1)
        
        # 定義顏色對應：綠 -> 黃 -> 紅
        cmap = ListedColormap(['#2ca02c', '#ff7f0e', '#d62728'])
        norm = BoundaryNorm([0, 1.05, 1.2, 5.0], cmap.N)
        
        lc = LineCollection(segments_list, cmap=cmap, norm=norm, linewidths=2)
        lc.set_array(ratios[1:]) # 使用後一項的比值
        line = ax.add_collection(lc)
        ax.plot(points[:, 0], points[:, 1], 'k.', markersize=2, alpha=0.3)
        
        # 標註嚴重跳躍點
        bad_mask = (ratios > 1.2) | (ratios < 0.833)
        if np.any(bad_mask):
            ax.scatter(points[bad_mask, 0], points[bad_mask, 1], color='red', marker='x', s=50, label='Jump > 1.2')

        return line

    return None

def main():
    parser = argparse.ArgumentParser(description="Visualize 2D geometry .dat files.")
    parser.add_argument("dat_file", nargs='?', help="Path to the .dat file")
    parser.add_argument("--config", help="Optional path to the JSON config file", default=None)
    parser.add_argument("--quality", action="store_true", help="Enable quality check heatmap")
    args = parser.parse_args()

    plt.figure(figsize=(12, 9))
    ax = plt.gca()
    
    last_lc = None
    if args.config and os.path.exists(args.config):
        with open(args.config, 'r') as f:
            config = json.load(f)
        elements = config.get("elements", [config]) # 兼容舊格式
        for idx, el in enumerate(elements):
            res = plot_element(ax, el, idx+1, args.quality)
            if args.quality and res: last_lc = res
        
        if args.quality and last_lc:
            cbar = plt.colorbar(last_lc, ax=ax, orientation='vertical', fraction=0.046, pad=0.04)
            cbar.set_label('Expansion Ratio ($ds_{i+1}/ds_i$)')
        elif not args.quality:
            ax.legend(loc='upper right', fontsize='x-small')
    elif args.dat_file:
        pts = np.loadtxt(args.dat_file)
        ax.plot(pts[:, 0], pts[:, 1], 'k.-', alpha=0.5)

    ax.set_aspect('equal')
    ax.set_title("Surface Resampler Pro" + (" - Quality Mode" if args.quality else ""))
    ax.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
