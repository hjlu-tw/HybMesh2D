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

    # 載入該元素的原始點供 file 類型參考
    global_points = None
    if "input_file" in element_config and os.path.exists(element_config["input_file"]):
        try:
            global_points = np.loadtxt(element_config["input_file"])
        except: pass

    segments = element_config.get("segments", [])
    current_idx = 0
    
    # 為每個 Element 使用不同的顏色循環
    for i, seg in enumerate(segments):
        seg_id = seg.get("id", "?")
        
        # 計算點數
        n_points = seg.get("parameters", {}).get("n_points")
        if n_points is None:
            if seg.get("type") == "file":
                start_idx = seg.get("start_index", 0)
                end_idx = seg.get("end_index", 0)
                if end_idx == -1 and global_points is not None: end_idx = len(global_points) - 1
                n_points = end_idx - start_idx + 1
            else:
                n_points = 50
        
        start = current_idx
        # 如果是最後一個線段，直接取到最後一個點，以包含自動產生的閉合點
        if i == len(segments) - 1:
            end = len(points)
        else:
            end = current_idx + n_points
            
        if end > len(points): end = len(points)
        if start >= len(points): break

        seg_points = points[start:end]
        label = f"E{element_id}-Seg{seg_id}"
        plt.plot(seg_points[:, 0], seg_points[:, 1], '.-', markersize=4, linewidth=1.5, label=label)
        
        # 預測下一段
        if i < len(segments) - 1:
            p_curr_end = get_seg_endpoints(seg, global_points)[1]
            p_next_start = get_seg_endpoints(segments[i+1], global_points)[0]
            if p_curr_end is not None and p_next_start is not None:
                if np.linalg.norm(p_curr_end - p_next_start) < 1e-9:
                    current_idx = end - 1
                else:
                    current_idx = end
            else:
                current_idx = end
        else:
            current_idx = end
            
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
                
            plt.legend(loc='upper right', title="Element-Segment IDs", framealpha=0.8, fontsize='small', ncol=2)
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
