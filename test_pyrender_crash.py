import os
print("Setting env vars...")
os.environ["PYOPENGL_PLATFORM"] = "pyglet"
import sys
import traceback

try:
    print("Importing pyrender...")
    import pyrender
    print("Pyrender imported.")
    
    print("Creating OffscreenRenderer...")
    r = pyrender.OffscreenRenderer(viewport_width=400, viewport_height=200)
    print("OffscreenRenderer created successfully!")
    r.delete()
    print("Deleted renderer.")
except Exception:
    traceback.print_exc()
