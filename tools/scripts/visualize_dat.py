#!/usr/bin/env python3
"""
Visualize 2D geometry .dat files.
Usage: python visualize_dat.py <path_to_dat_file>
"""

import sys
import os
import matplotlib.pyplot as plt
import numpy as np

def main():
    if len(sys.argv) < 2:
        print("Usage: python visualize_dat.py <path_to_dat_file>")
        sys.exit(1)

    dat_file = sys.argv[1]
    if not os.path.exists(dat_file):
        print(f"Error: File '{dat_file}' not found.")
        sys.exit(1)

    try:
        # Try loading with numpy, assuming whitespace separated X Y
        points = np.loadtxt(dat_file)
    except Exception as e:
        print(f"Error loading {dat_file}: {e}")
        sys.exit(1)

    if points.ndim != 2 or points.shape[1] < 2:
        print(f"Error: Expected 2D points (X Y) in {dat_file}, but got shape {points.shape}")
        sys.exit(1)

    x = points[:, 0]
    y = points[:, 1]

    # If it's a closed loop, append the first point to the end to close the drawing
    # Note: Usually these .dat files are for boundaries. 
    # Let's check if first and last points are close.
    if len(points) > 1:
        dist = np.linalg.norm(points[0] - points[-1])
        if dist > 1e-6:
            # If not closed, let's just plot as is, or maybe the user wants it closed?
            # We'll just plot them and add markers.
            pass

    plt.figure(figsize=(10, 8))
    plt.plot(x, y, 'b-', alpha=0.5, label='Lines')
    plt.plot(x, y, 'r.', markersize=4, label='Points')
    
    plt.gca().set_aspect('equal')
    plt.xlabel('X')
    plt.ylabel('Y')
    plt.title(f"Geometry Visualization: {os.path.basename(dat_file)}")
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend()
    
    # Annotate point counts
    plt.figtext(0.15, 0.02, f"Total points: {len(points)}", fontsize=10)

    print(f"Showing plot for {dat_file} ({len(points)} points)...")
    plt.show()

if __name__ == "__main__":
    main()
