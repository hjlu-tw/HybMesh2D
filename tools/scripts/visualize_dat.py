#!/usr/bin/env python3
"""
Visualize 2D geometry .dat files.
Usage: python visualize_dat.py <path_to_dat_file>
"""

import sys
import os
import matplotlib.pyplot as plt
import numpy as np
import json
import argparse

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

    plt.figure(figsize=(10, 8))
    
    # Base plot
    plt.plot(points[:, 0], points[:, 1], 'k-', alpha=0.3, label='Full Geometry')
    plt.plot(points[:, 0], points[:, 1], 'r.', markersize=2, alpha=0.5)

    # If config is provided, try to highlight segments
    if args.config and os.path.exists(args.config):
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
            
            # Since the resampled output combines points, we need to track indices
            # The surface_resampler processes segments in order.
            current_idx = 0
            for seg in config.get("segments", []):
                seg_id = seg.get("id", "?")
                
                # Get number of points for this segment
                n_points = seg.get("parameters", {}).get("n_points")
                if n_points is None:
                    # Fallback for file type if n_points not specified
                    if seg.get("type") == "file":
                        n_points = seg.get("end_index", 0) - seg.get("start_index", 0) + 1
                    else:
                        n_points = 50 # Default
                
                start = current_idx
                end = current_idx + n_points
                
                if end > len(points):
                    end = len(points)
                
                if start < len(points):
                    seg_points = points[start:end]
                    # 使用 '.-' 同時顯示線段與格點，並透過 label 讓圖例顯示 ID
                    plt.plot(seg_points[:, 0], seg_points[:, 1], '.-', markersize=6, linewidth=2, label=f'Seg {seg_id}')
                    
                    current_idx = end - 1 # Segments share a joint point
            
            # 將圖例固定在右上角，方便查看 ID
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
