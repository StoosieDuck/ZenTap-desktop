"""
Standalone test to render USBC_key_v2.glb with pyrender
"""
import os
os.environ['PYOPENGL_PLATFORM'] = 'pyglet'  # Force pyglet backend

import trimesh
import pyrender
import numpy as np
from PIL import Image

print("1. Loading GLB...")
scene = trimesh.load("USBC_key_v2.glb")
print(f"   Loaded scene with bounds: {scene.bounds}")
print(f"   Extents: {scene.extents}")

print("2. Creating pyrender scene...")
pr_scene = pyrender.Scene(ambient_light=[0.3, 0.3, 0.3])

# Add meshes from trimesh scene
for name, geom in scene.geometry.items():
    print(f"   Adding mesh: {name}")
    mesh = pyrender.Mesh.from_trimesh(geom)
    # Get the transform for this geometry
    transform = scene.graph.get(name)[0] if name in scene.graph.nodes else np.eye(4)
    pr_scene.add(mesh, pose=transform)

print(f"   Total nodes in scene: {len(pr_scene.nodes)}")

# Calculate camera distance based on model size
max_extent = max(scene.extents)
camera_distance = max_extent * 2.5
print(f"   Camera distance: {camera_distance}")

# Add camera
camera = pyrender.PerspectiveCamera(yfov=np.pi / 4.0, aspectRatio=2.0)
camera_pose = np.eye(4)
camera_pose[2, 3] = camera_distance  # Move back on Z
camera_pose[1, 3] = max_extent * 0.3  # Move up slightly
pr_scene.add(camera, pose=camera_pose)

# Add lights
light = pyrender.DirectionalLight(color=np.ones(3), intensity=3.0)
light_pose = np.eye(4)
light_pose[:3, :3] = trimesh.transformations.euler_matrix(np.pi/4, np.pi/4, 0)[:3, :3]
pr_scene.add(light, pose=light_pose)

# Add ambient point light
point_light = pyrender.PointLight(color=np.ones(3), intensity=20.0)
point_pose = np.eye(4)
point_pose[:3, 3] = [0, max_extent, camera_distance]
pr_scene.add(point_light, pose=point_pose)

print("3. Creating renderer...")
try:
    renderer = pyrender.OffscreenRenderer(800, 400)
    print("   Renderer created!")
    
    print("4. Rendering...")
    color, depth = renderer.render(pr_scene)
    print(f"   Rendered! Output shape: {color.shape}")
    
    img = Image.fromarray(color)
    img.save("test_render_output.png")
    print("   Saved to test_render_output.png")
    
    renderer.delete()
    print("5. Done!")
    
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()
