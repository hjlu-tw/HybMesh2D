import matplotlib.pyplot as plt
import numpy as np
import json
import subprocess
import os
import sys

class SurfaceResamplerGUI:
    def __init__(self, dat_file):
        self.dat_file = dat_file
        self.points = self.load_dat(dat_file)
        self.split_indices = [0, len(self.points) - 1]
        self.segments_info = []
        
        self.fig, self.ax = plt.subplots(figsize=(10, 8))
        self.ax.set_title(f"Surface Resampler - {os.path.basename(dat_file)}\nClick to add split points. Press 'Enter' to finish.")
        self.plot_geometry()
        
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        
        print("Instructions:")
        print("- Left Click: Add/Remove split point (snaps to nearest vertex)")
        print("- Enter: Confirm segments and generate JSON")
        print("- Escape: Clear all split points")
        
        plt.show()

    def load_dat(self, filename):
        return np.loadtxt(filename)

    def plot_geometry(self):
        self.ax.clear()
        self.ax.plot(self.points[:, 0], self.points[:, 1], 'b-', alpha=0.3)
        self.ax.scatter(self.points[:, 0], self.points[:, 1], c='gray', s=10, picker=5)
        
        # Highlight split points
        sorted_indices = sorted(list(set(self.split_indices)))
        for idx in sorted_indices:
            self.ax.plot(self.points[idx, 0], self.points[idx, 1], 'ro')
            self.ax.text(self.points[idx, 0], self.points[idx, 1], f"Idx:{idx}", color='red')
        
        self.ax.set_aspect('equal')
        self.fig.canvas.draw()

    def on_click(self, event):
        if event.inaxes != self.ax: return
        
        # Find nearest point index
        dists = np.sqrt((self.points[:, 0] - event.xdata)**2 + (self.points[:, 1] - event.ydata)**2)
        nearest_idx = np.argmin(dists)
        
        if nearest_idx in self.split_indices:
            if nearest_idx not in [0, len(self.points)-1]:
                self.split_indices.remove(nearest_idx)
        else:
            self.split_indices.append(nearest_idx)
        
        self.plot_geometry()

    def on_key(self, event):
        if event.key == 'enter':
            self.process_segments()
        elif event.key == 'escape':
            self.split_indices = [0, len(self.points) - 1]
            self.plot_geometry()

    def process_segments(self):
        sorted_indices = sorted(list(set(self.split_indices)))
        segments = []
        
        print("\n--- Segment Configuration ---")
        for i in range(len(sorted_indices) - 1):
            start = sorted_indices[i]
            end = sorted_indices[i+1]
            print(f"Segment {i+1}: Index {start} to {end}")
            
            # Simple CLI input for demonstration; in a full GUI this would be a popup/dialog
            try:
                n_points = int(input(f"  Enter target number of points for Segment {i+1} (default 50): ") or "50")
            except ValueError:
                n_points = 50
                
            segments.append({
                "id": i + 1,
                "start_index": int(start),
                "end_index": int(end),
                "strategy": "uniform",
                "parameters": {"n_points": n_points}
            })
        
        is_closed_input = input("\nIs this geometry a closed loop? (y/n) [default: y]: ").strip().lower()
        is_closed = is_closed_input != 'n'

        output_file = self.dat_file.replace(".dat", "_resampled.dat")
        config = {
            "input_file": self.dat_file,
            "output_file": output_file,
            "is_closed": is_closed,
            "segments": segments
        }
        
        config_path = "gui_config.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
            
        print(f"\nConfig saved to {config_path}")
        
        # Call C++ Backend
        resampler_bin = "./build/surface_resampler"
        if os.path.exists(resampler_bin):
            print("Running C++ Backend...")
            result = subprocess.run([resampler_bin, config_path], capture_output=True, text=True)
            print(result.stdout)
            if result.returncode == 0:
                print(f"Success! Result saved to {output_file}")
                # Plot result
                resampled_points = np.loadtxt(output_file)
                plt.figure()
                plt.plot(resampled_points[:, 0], resampled_points[:, 1], 'r.-', label='Resampled')
                plt.title("Resampling Result")
                plt.gca().set_aspect('equal')
                plt.legend()
                plt.show()
        else:
            print(f"Error: Backend binary {resampler_bin} not found. Please compile first.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <path_to_dat_file>")
    else:
        SurfaceResamplerGUI(sys.argv[1])
