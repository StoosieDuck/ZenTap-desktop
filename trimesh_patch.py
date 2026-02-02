import trimesh
import trimesh.viewer
import trimesh.viewer.windowed
import logging

print("Applying robust trimesh patch...")

try:
    # Patch 1: _update_perspective
    # This is where the division by zero actually happens
    original_update_perspective = trimesh.viewer.windowed.SceneViewer._update_perspective
    
    def patched_update_perspective(self, width, height):
        if height <= 0: 
            height = 1
        if width <= 0:
            width = 1
        return original_update_perspective(self, width, height)
        
    trimesh.viewer.windowed.SceneViewer._update_perspective = patched_update_perspective
    print("Patched _update_perspective")

    # Patch 2: on_resize
    # Prevent propagation of invalid sizes
    original_on_resize = trimesh.viewer.windowed.SceneViewer.on_resize
    
    def patched_on_resize(self, width, height):
        if width <= 0 or height <= 0:
            return
        return original_on_resize(self, width, height)
        
    trimesh.viewer.windowed.SceneViewer.on_resize = patched_on_resize
    print("Patched on_resize")
    
    # Patch 3: Force transparent/black background
    original_init = trimesh.viewer.windowed.SceneViewer.__init__
    def patched_init(self, scene, **kwargs):
        # Force background to transparent black
        kwargs['background'] = [0, 0, 0, 0] 
        original_init(self, scene, **kwargs)
        # Ensure it sticks
        self.background = [0, 0, 0, 0]
        
    trimesh.viewer.windowed.SceneViewer.__init__ = patched_init
    print("Patched SceneViewer.__init__")
    
except Exception as e:
    print(f"Error applying trimesh patch: {e}")
