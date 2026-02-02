import trimesh
import numpy as np

print("Loading GLB...")
scene = trimesh.load("USBC_key_v2.glb")
print(f"Type: {type(scene)}")

# Get geometry info
if hasattr(scene, 'geometry'):
    for name, geom in scene.geometry.items():
        print(f"  Geometry '{name}': {geom.vertices.shape[0]} vertices")
        if hasattr(geom, 'bounds'):
            print(f"    Bounds: {geom.bounds}")

# Try getting bounding box of entire scene
try:
    bounds = scene.bounds
    print(f"Scene bounds: {bounds}")
    extents = scene.extents
    print(f"Scene extents (size): {extents}")
    centroid = scene.centroid
    print(f"Scene centroid: {centroid}")
except Exception as e:
    print(f"Could not get bounds: {e}")

# Dump the scene graph
if hasattr(scene, 'graph'):
    print(f"Graph nodes: {list(scene.graph.nodes)}")
