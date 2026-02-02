import trimesh
import pyrender
import numpy as np
from PIL import Image

print("Loading GLB...")
scene = trimesh.load("USBC_key_v2.glb")
print(f"Loaded: {type(scene)}")

# Check bounds
if hasattr(scene, 'bounds'):
    print(f"Bounds: {scene.bounds}")
if hasattr(scene, 'extents'):
    print(f"Extents: {scene.extents}")

# Convert to pyrender scene
print("Converting to pyrender...")
pr_scene = pyrender.Scene.from_trimesh_scene(scene)
print(f"Nodes: {len(pr_scene.nodes)}")

# Add camera
camera = pyrender.PerspectiveCamera(yfov=np.pi / 3.0, aspectRatio=2.0)
camera_pose = np.eye(4)
camera_pose[2, 3] = 0.3  # Back
pr_scene.add(camera, pose=camera_pose)

# Add light
light = pyrender.DirectionalLight(color=np.ones(3), intensity=5.0)
pr_scene.add(light, pose=np.eye(4))

# Render
print("Creating renderer...")
renderer = pyrender.OffscreenRenderer(400, 200)
print("Rendering...")
try:
    color, depth = renderer.render(pr_scene)
    print(f"Rendered! Shape: {color.shape}")
    img = Image.fromarray(color)
    img.save("test_render.png")
    print("Saved to test_render.png")
except Exception as e:
    print(f"Render failed: {e}")
finally:
    renderer.delete()
