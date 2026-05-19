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

def main():
    parser = argparse.ArgumentParser(description="Visualize 2D geometry .dat files.")
    parser.add_argument("dat_file", help="Path to the .dat file")
    parser.add_argument("--config", help="Optional path to the JSON config file to show segment IDs", default=None)
    args = parser.parse_args()

    dat_file = args.dat_file
    if not os.path.exists(dat_file):
        print(f"Error: File '{dat_file}' not found.")
        sys.exit(1)

    try:
        points = np.loadtxt(dat_file)
    except Exception as e:
        print(f"Error loading {dat_file}: {e}")
        sys.exit(1)

    if points.ndim != 2 or points.shape[1] < 2:
        print(f"Error: Expected 2D points (X Y) in {dat_file}, but got shape {points.shape}")
        sys.exit(1)

    plt.figure(figsize=(12, 9))
    
    # Base plot
    plt.plot(points[:, 0], points[:, 1], 'k-', alpha=0.3, label='Full Geometry')
    plt.plot(points[:, 0], points[:, 1], 'r.', markersize=2, alpha=0.3)

    if args.config and os.path.exists(args.config):
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
            
            # 載入全域資料點供 file 類型參考
            global_points = None
            if "input_file" in config and os.path.exists(config["input_file"]):
                try:
                    global_points = np.loadtxt(config["input_file"])
                except:
                    pass

            segments = config.get("segments", [])
            current_idx = 0
            
            for i in range(len(segments)):
                seg = segments[i]
                seg_id = seg.get("id", "?")
                
                # 計算該段點數 (與 C++ main.cpp 同步)
                n_points = seg.get("parameters", {}).get("n_points")
                if n_points is None:
                    if seg.get("type") == "file":
                        start_idx = seg.get("start_index", 0)
                        end_idx = seg.get("end_index", 0)
                        if end_idx == -1 and global_points is not None: 
                            end_idx = len(global_points) - 1
                        n_points = end_idx - start_idx + 1
                    else:
                        n_points = 50
                
                start = current_idx
                end = current_idx + n_points
                
                if end > len(points): end = len(points)
                if start >= len(points): break

                seg_points = points[start:end]
                plt.plot(seg_points[:, 0], seg_points[:, 1], '.-', markersize=6, linewidth=2, label=f'Seg {seg_id}')
                
                # 判斷下一段是否與當前段理論上相連
                if i < len(segments) - 1:
                    next_seg = segments[i+1]
                    _, p_end = get_seg_endpoints(seg, global_points)
                    p_start_next, _ = get_seg_endpoints(next_seg, global_points)
                    
                    if p_end is not None and p_start_next is not None:
                        dist = np.linalg.norm(p_end - p_start_next)
                        # 如果理論上起點終點相同，代表 C++ 端會執行 pop_back() 合併點
                        if dist < 1e-9:
                            current_idx = end - 1 # 共享點
                        else:
                            current_idx = end     # 不相連
                    else:
                        current_idx = end
                else:
                    current_idx = end
            
            if current_idx < len(points):
                plt.plot(points[current_idx-1:, 0], points[current_idx-1:, 1], 'k--', alpha=0.5, label='Closed Link')
            
            plt.legend(loc='upper right', title="Segment IDs", framealpha=0.9)
        except Exception as e:
            print(f"Warning: Could not process config for labels: {e}")

    plt.gca().set_aspect('equal')
    plt.xlabel('X')
    plt.ylabel('Y')
    plt.title(f"Geometry Visualization: {os.path.basename(dat_file)}")
    plt.grid(True, linestyle='--', alpha=0.6)
    
    # Annotate point counts
    plt.figtext(0.15, 0.02, f"Total points: {len(points)}", fontsize=10)

    print(f"Showing plot for {dat_file} ({len(points)} points)...")
    plt.show()

if __name__ == "__main__":
    main()
