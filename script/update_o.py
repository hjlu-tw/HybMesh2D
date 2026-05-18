import numpy as np
import os

spacing = 0.002 
output_dir = "geometries"
os.makedirs(output_dir, exist_ok=True)

def interpolate_points(polygon, target_spacing):
    dense_points = []
    for i in range(len(polygon)):
        p1 = np.array(polygon[i])
        p2 = np.array(polygon[(i + 1) % len(polygon)])
        dist = np.linalg.norm(p2 - p1)
        if dist < 1e-9: continue
        num_segments = max(int(round(dist / target_spacing)), 1)
        for j in range(num_segments):
            point = p1 + (p2 - p1) * (j / num_segments)
            dense_points.append(point)
    return dense_points

def save_geometry(name, points):
    filename = os.path.join(output_dir, f"{name}_dense.dat")
    with open(filename, "w") as f:
        for p in points:
            f.write(f"{p[0]:.6f} {p[1]:.6f}\n")
    print(f"Generated: {filename} ({len(points)} points)")

letters = {
    "U": [(0.2, 0.8), (0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.6, 0.8), (0.6, 0.4), (0.4, 0.4), (0.4, 0.8)],
    "N": [(0.2, 0.2), (0.2, 0.8), (0.4, 0.8), (0.6, 0.4), (0.6, 0.8), (0.8, 0.8), (0.8, 0.2), (0.6, 0.2), (0.4, 0.6), (0.4, 0.2)],
    "I": [(0.4, 0.2), (0.4, 0.8), (0.6, 0.8), (0.6, 0.2)],
    "C": [(0.8, 0.6), (0.8, 0.8), (0.2, 0.8), (0.2, 0.2), (0.8, 0.2), (0.8, 0.4), (0.6, 0.4), (0.6, 0.35), (0.4, 0.35), (0.4, 0.65), (0.6, 0.65), (0.6, 0.6)],
    "O": [(0.2, 0.2), (0.2, 0.8), (0.8, 0.8), (0.8, 0.2)], # Simple outer box for O
    "E": [(0.2, 0.2), (0.2, 0.8), (0.8, 0.8), (0.8, 0.65), (0.4, 0.65), (0.4, 0.55), (0.7, 0.55), (0.7, 0.45), (0.4, 0.45), (0.4, 0.35), (0.8, 0.35), (0.8, 0.2)],
    "S": [(0.2, 0.2), (0.8, 0.2), (0.8, 0.55), (0.4, 0.55), (0.4, 0.65), (0.8, 0.65), (0.8, 0.8), (0.2, 0.8), (0.2, 0.45), (0.6, 0.45), (0.6, 0.35), (0.2, 0.35)]
}

for char, poly in letters.items():
    dense_poly = interpolate_points(poly, spacing)
    save_geometry(char, dense_poly)

full_geom = []
for i, char in enumerate("UNICONES"):
    poly = letters[char]
    offset_poly = [(p[0] + i * 1.0, p[1]) for p in poly]
    full_geom.extend(interpolate_points(offset_poly, spacing))

save_geometry("UNICONES", full_geom)
