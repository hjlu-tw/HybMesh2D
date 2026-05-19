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
    
    if seg_type == "file":
        if global_points is None: return None, None
        start_idx = seg.get("start_index", 0)
        end_idx = seg.get("end_index", 0)
        if end_idx == -1: end_idx = len(global_points) - 1
        if start_idx < len(global_points) and end_idx < len(global_points):
            return global_points[start_idx], global_points[end_idx]
        return None, None
    
    formula = seg.get("formula", "line")
    rng = params.get("range", [0.0, 1.0])
    
    if formula == "sin":
        amp = params.get("amplitude", 1.0)
        freq = params.get("frequency", 1.0)
        phase = params.get("phase", 0.0)
        off_y = params.get("offset_y", 0.0)
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
    
    else: # Custom formula
        try:
            # 簡單替換語法以符合 Python
            py_formula = formula.replace("^", "**").replace("sin", "np.sin").replace("cos", "np.cos").replace("exp", "np.exp").replace("sqrt", "np.sqrt")
            f = lambda x: eval(py_formula, {"np": np, "x": x, "sin": np.sin, "cos": np.cos, "exp": np.exp, "sqrt": np.sqrt, "abs": np.abs})
            return np.array([rng[0], f(rng[0])]), np.array([rng[1], f(rng[1])])
        except:
            return None, None

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

def plot_element(plt, element_config, element_id, global_offset_idx):
    """繪製單個元素及其線段"""
    output_file = element_config.get("output_file")
    if not output_file or not os.path.exists(output_file):
        print(f"Warning: Output file {output_file} not found for element.")
        return 0

    try:
        points = np.loadtxt(output_file)
    except:
        return 0

    # 載入該元素的原始點
    global_points = None
    if "input_file" in element_config and os.path.exists(element_config["input_file"]):
        try:
            global_points = np.loadtxt(element_config["input_file"])
            # 如果是閉合，預先補點 (與 C++ 同步)
            if element_config.get("is_closed", False):
                d = np.linalg.norm(global_points[0] - global_points[-1])
                if d > 1e-9:
                    global_points = np.vstack([global_points, global_points[0]])
        except: pass

    segments = element_config.get("segments", [])
    current_idx = 0
    
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
            start_idx = seg.get("start_index", 0)
            end_idx = seg.get("end_index", -1)
            if end_idx == -1 and global_points is not None: end_idx = len(global_points) - 1
            
            if auto_split and global_points is not None:
                sub_pts = global_points[start_idx : end_idx + 1]
                local_features = detect_feature_points(sub_pts, split_threshold)
                for f in range(len(local_features) - 1):
                    sub_ranges.append((start_idx + local_features[f], start_idx + local_features[f+1]))
            else:
                sub_ranges.append((start_idx, end_idx))

        # 針對每個子區段繪圖
        for sub_idx, sub_range in enumerate(sub_ranges):
            # 準備點
            if seg_type == "curve":
                formula = seg.get("formula", "line")
                p_start, p_end = get_seg_endpoints(seg, global_points)
                # 對於 Curve，我們計算起點終點直線距離作為近似長度來估算點數
                # 較精確做法應在 get_seg_endpoints 中回傳長度，此處先以點數判斷
                segment_points_for_len = [] 
            else:
                segment_points_for_len = global_points[sub_range[0] : sub_range[1] + 1]

            # 計算該段理論點數 (優先使用 spacing)
            n_points = seg.get("parameters", {}).get("n_points")
            if seg.get("parameters", {}).get("spacing") is not None:
                ds = seg["parameters"]["spacing"]
                if len(segment_points_for_len) >= 2:
                    # 計算弧長
                    diffs = np.diff(segment_points_for_len, axis=0)
                    total_len = np.sum(np.sqrt(np.sum(diffs**2, axis=1)))
                    n_points = int(round(total_len / ds)) + 1
                else:
                    # 如果是 Curve 類型且只有 spacing，Python 端目前暫採預設 50 或簡單估算
                    n_points = 50 

            if n_points is None:
                if seg_type == "file":
                    n_points = sub_range[1] - sub_range[0] + 1
                else:
                    n_points = 50
            
            if n_points < 2: n_points = 2
            
            start = current_idx
            # 如果是該 Element 的最後一段的最後一個子段，取到最後一個點
            if i == len(segments) - 1 and sub_idx == len(sub_ranges) - 1:
                end = len(points)
            else:
                end = current_idx + n_points
            
            if end > len(points): end = len(points)
            if start >= len(points): break

            seg_points = points[start:end]
            label = f"E{element_id}-S{seg_id}"
            if len(sub_ranges) > 1:
                label += f"-{sub_idx+1}"
            
            plt.plot(seg_points[:, 0], seg_points[:, 1], '.-', markersize=4, linewidth=1.5, label=label)
            current_idx = end - 1
            
    return len(points)

def main():
    parser = argparse.ArgumentParser(description="Visualize 2D geometry .dat files.")
    parser.add_argument("dat_file", nargs='?', help="Path to the .dat file (ignored if --config is used with multiple elements)")
    parser.add_argument("--config", help="Optional path to the JSON config file to show segment IDs", default=None)
    args = parser.parse_args()

    plt.figure(figsize=(12, 9))
    total_points_loaded = 0

    if args.config and os.path.exists(args.config):
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
            
            if "elements" in config and isinstance(config["elements"], list):
                for idx, element in enumerate(config["elements"]):
                    total_points_loaded += plot_element(plt, element, idx + 1, total_points_loaded)
            else:
                total_points_loaded = plot_element(plt, config, 1, 0)
                
            plt.legend(loc='upper right', title="Element-Segment IDs", framealpha=0.8, fontsize='x-small', ncol=1)
        except Exception as e:
            print(f"Error processing config: {e}")
            import traceback
            traceback.print_exc()
    elif args.dat_file:
        try:
            points = np.loadtxt(args.dat_file)
            plt.plot(points[:, 0], points[:, 1], 'k.-', alpha=0.5, label='Raw Data')
            total_points_loaded = len(points)
        except Exception as e:
            print(f"Error loading {args.dat_file}: {e}")
            sys.exit(1)
    else:
        print("Error: Must provide a .dat file or a --config file.")
        sys.exit(1)

    plt.gca().set_aspect('equal')
    plt.xlabel('X')
    plt.ylabel('Y')
    plt.title(f"Geometry Visualization")
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.figtext(0.15, 0.02, f"Total points shown: {total_points_loaded}", fontsize=10)
    plt.show()

if __name__ == "__main__":
    main()
