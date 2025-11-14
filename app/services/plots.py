import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.interpolate import griddata

data = {
    "pad_id": ["P01","P02","P03","P04","P05","P06","P07","P08","P09","P10","P11","P12","P13","P14","P15","P16"],
    "x_mm":  [-6,-2,2,6,-6,-2,2,6,-6,-2,2,6,-6,-2,2,6],
    "y_mm":  [-6,-6,-6,-6,-2,-2,-2,-2,2,2,2,2,6,6,6,6],
    "warpage_um": [
        101.88288, 56.60160, 56.60160, 101.88288,
        56.60160, 11.32032, 11.32032, 56.60160,
        56.60160, 11.32032, 11.32032, 56.60160,
        101.88288, 56.60160, 56.60160, 101.88288
    ]
}

df = pd.DataFrame(data)
df["warpage_mm"] = df["warpage_um"] / 1000.0  # convert to mm

# -------------------
# Prepare interpolation grid
# -------------------
x = df["x_mm"].values
y = df["y_mm"].values
z = df["warpage_mm"].values

# create smooth grid (100x100)
grid_x, grid_y = np.mgrid[min(x):max(x):100j, min(y):max(y):100j]

# bicubic interpolation (cubic)
grid_z = griddata((x, y), z, (grid_x, grid_y), method='cubic')

# -------------------
# Plot
# -------------------
fig = plt.figure(figsize=(10, 7))
ax = fig.add_subplot(111, projection='3d')

# smooth surface
surf = ax.plot_surface(
    grid_x, grid_y, grid_z,
    linewidth=0, antialiased=True
)

# optional: scatter actual pad points
ax.scatter(x, y, z, color='black')

ax.set_xlabel("X (mm)")
ax.set_ylabel("Y (mm)")
ax.set_zlabel("Warpage (mm)")
ax.set_title("Smooth 3D Warpage Surface (Bicubic Interpolation)")

plt.tight_layout()# -------------------
# Prepare interpolation grid
# -------------------
x = df["x_mm"].values
y = df["y_mm"].values
z = df["warpage_mm"].values

# create smooth grid (100x100)
grid_x, grid_y = np.mgrid[min(x):max(x):100j, min(y):max(y):100j]

# bicubic interpolation (cubic)
grid_z = griddata((x, y), z, (grid_x, grid_y), method='cubic')

# -------------------
# Plot
# -------------------
fig = plt.figure(figsize=(10, 7))
ax = fig.add_subplot(111, projection='3d')

# smooth surface
surf = ax.plot_surface(
    grid_x, grid_y, grid_z,
    linewidth=0, antialiased=True
)

# optional: scatter actual pad points
ax.scatter(x, y, z, color='black')

ax.set_xlabel("X (mm)")
ax.set_ylabel("Y (mm)")
ax.set_zlabel("Warpage (mm)")
ax.set_title("Smooth 3D Warpage Surface (Bicubic Interpolation)")

plt.tight_layout()

plt.savefig("plot2.png", dpi=300, bbox_inches="tight")