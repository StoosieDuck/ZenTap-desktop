"""
Test trimesh's built-in rendering (uses pyglet internally)
"""
import trimesh
import numpy as np
from PIL import Image

print("Loading GLB...")
scene = trimesh.load("USBC_key_v2.glb")
print(f"Scene loaded. Extents: {scene.extents}")

# Try to render using trimesh's SceneViewer in headless mode
try:
    # Render to PNG directly using trimesh
    png_data = scene.save_image(resolution=[800, 400], visible=False)
    print(f"Got image data: {len(png_data)} bytes")
    
    # Save to file
    with open("trimesh_render.png", "wb") as f:
        f.write(png_data)
    print("Saved to trimesh_render.png")
    
except Exception as e:
    print(f"Trimesh render failed: {e}")
    import traceback
    traceback.print_exc()
