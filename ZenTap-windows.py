import tkinter as tk
from tkinter import messagebox, ttk
import psutil
import threading
import time
import os
import sys
import ctypes
import math
from ctypes import wintypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1) # Enable High DPI
except:
    ctypes.windll.user32.SetProcessDPIAware()


APP_FONT_BOLD = ("Roboto Medium", 12)
APP_FONT_NORMAL = ("Roboto", 12)
APP_FONT_TITLE = ("Roboto Medium", 24)
APP_FONT_HUGE = ("Roboto Medium", 32)
APP_FONT_MONO = ("Consolas", 10)

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageFilter
    import pygetwindow as gw
    import pyautogui
    
    # 3D Rendering Imports with Safety
    os.environ["PYOPENGL_PLATFORM"] = "pyglet" # Force pyglet backend which worked in tests
    
    import trimesh
    try:
        import trimesh_patch # Apply robust fixes
    except ImportError:
        pass
        
    # import pyrender # unused
    import numpy as np
except Exception as e:
    import traceback
    error_msg = f"Missing libraries or initialization error: {e}\n\nTraceback:\n{traceback.format_exc()}"
    print(error_msg)
    messagebox.showerror("Error", "Missing libraries or 3D Initialization failed.\n\n" + str(e))
    sys.exit()

# --- 2. WINDOWS API ---
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
shell32 = ctypes.windll.shell32

SHGFI_ICON = 0x000000100
SHGFI_LARGEICON = 0x000000000

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
                ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG), ('biYPelsPerMeter', wintypes.LONG),
                ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', wintypes.DWORD * 3)]

USE_SHORTCUT_RESOLVER = False
try:
    import win32com.client
    import pythoncom
    USE_SHORTCUT_RESOLVER = True
except ImportError:
    pass

APP_MAP = {
    "Microsoft Edge": "msedge.exe",
    "Visual Studio Code": "code.exe",
    "Apple Music": "AppleMusic.exe",
    "Chrome": "chrome.exe",
    "Spotify": "Spotify.exe",
    "Firefox": "firefox.exe",
    "Discord": "discord.exe",
    "Steam": "steam.exe"
}

# --- 3. HELPER FUNCTIONS ---
def resolve_shortcut(lnk_path):
    if not USE_SHORTCUT_RESOLVER: return lnk_path
    try:
        shell_obj = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell_obj.CreateShortCut(lnk_path)
        target = shortcut.Targetpath
        if target and os.path.exists(target): return target
    except: pass
    return lnk_path

def icon_to_image(hIcon, size=64):
    if not hIcon: return None
    hdc = user32.GetDC(0)
    mem_dc = gdi32.CreateCompatibleDC(hdc)
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = size
    bmi.bmiHeader.biHeight = -size
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bits = ctypes.c_void_p()
    hBitmap = gdi32.CreateDIBSection(mem_dc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    old_obj = gdi32.SelectObject(mem_dc, hBitmap)
    user32.DrawIconEx(mem_dc, 0, 0, hIcon, size, size, 0, None, 0x0003)
    raw_data = ctypes.string_at(bits, size * size * 4)
    img = Image.frombuffer('RGBA', (size, size), raw_data, 'raw', 'BGRA', 0, 1)
    gdi32.SelectObject(mem_dc, old_obj)
    gdi32.DeleteObject(hBitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(0, hdc)
    user32.DestroyIcon(hIcon)
    return img

def get_file_icon(path):
    if not os.path.exists(path): return None
    hIcon = wintypes.HICON()
    try:
        if user32.PrivateExtractIconsW(path, 0, 64, 64, ctypes.pointer(hIcon), 0, 1, 0) > 0:
            img = icon_to_image(hIcon, 64)
            if img: return img.resize((48, 48), Image.Resampling.LANCZOS)
    except: pass
    return None

def get_website_favicon(keyword):
    """Fetch favicon for a website keyword from Google's API or local folder."""
    import urllib.request
    import io
    
    # Clean keyword - extract domain if it looks like a URL
    domain = keyword.lower().strip()
    if not '.' in domain:
        domain = f"{domain}.com"  # Assume .com for simple keywords
    
    img = None
    
    # Try local folder first
    local_path = os.path.join(os.path.dirname(__file__), "website_icons", f"{keyword.lower()}.png")
    if os.path.exists(local_path):
        try:
            img = Image.open(local_path).resize((48, 48), Image.Resampling.LANCZOS)
        except: pass
    
    # Fetch from Google Favicon API
    if img is None:
        try:
            url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                img_data = response.read()
                img = Image.open(io.BytesIO(img_data))
                # Convert to RGBA if needed
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                img = img.resize((48, 48), Image.Resampling.LANCZOS)
        except Exception as e:
            print(f"Favicon fetch failed for {keyword}: {e}")
    
    # Round the corners if we have an image
    if img:
        img = round_icon_corners(img)
    
    return img

def round_icon_corners(img, radius_percent=0.24):
    """Round the corners of an image with supersampling for smooth edges."""
    from PIL import ImageDraw
    
    # Ensure RGBA
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    w, h = img.size
    
    # Supersampling: work at 4x resolution for smooth anti-aliased corners
    scale = 4
    big_w, big_h = w * scale, h * scale
    radius = int(min(big_w, big_h) * radius_percent)
    
    # Upscale image
    big_img = img.resize((big_w, big_h), Image.Resampling.LANCZOS)
    
    # Create high-res mask with rounded corners
    mask = Image.new('L', (big_w, big_h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, big_w, big_h), radius, fill=255)
    
    # Apply mask at high resolution
    output = Image.new('RGBA', (big_w, big_h), (0, 0, 0, 0))
    output.paste(big_img, mask=mask)
    
    # Downscale back to original size with high quality
    return output.resize((w, h), Image.Resampling.LANCZOS)


# --- UI COMPONENT: INTERACTIVE 3D CARD ---
# --- UI COMPONENT: INTERACTIVE 3D CARD ---
# --- UI COMPONENT: INTERACTIVE 3D CARD ---
class InteractiveCard(tk.Canvas):
    def __init__(self, parent, width=600, height=300, bg="white"):
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0)
        self.cx = width // 2
        self.cy = height // 2
        self.card_w = width
        self.card_h = height
        
        # 3D State
        self.use_3d = True 
        self.renderer = None
        self.scene = None
        self.camera_node = None
        self.usb_scene = None
        
        # Zoom Animation State
        self.zoom_target = 1.1 # Closer (Bigger)
        self.zoom_current = 1.1
        self.base_distance = 10.0 # Placeholder, set in init_3d
        
        # Helper to initialize 3D
        self.init_3d()

        # Load 2D fallback image (just in case)
        self.usb_img_2d = None
        if os.path.exists("USB_key.png"):
             try:
                img = Image.open("USB_key.png").convert("RGBA")
                target_width = 300
                aspect = img.height / img.width
                target_height = int(target_width * aspect)
                self.usb_img_2d = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
             except: pass

        # Create radial gradient shadow (cached)
        self.shadow_base = self.create_radial_gradient_shadow(380, 76) # Bigger shadow
        
        # Interaction State
        # Interaction State
        # Interaction State
        self.rotate_x = -90.0 # Pitch (Flip to Bottom view for Z logo)
        self.rotate_y = 90.0 # Yaw
        self.dragging = False
        
        
        # Zoom Animation State (Moved to top)
        self.start_x = 0
        self.start_y = 0
        
        # Hover animation
        self.hover_offset = 0.0
        self.hover_direction = 1
        
        # Photo refs
        self.photo_image = None
        self.shadow_photo = None
        
        # Initial draw
        self.draw_scene()
        
        # Bindings
        self.bind("<Button-1>", self.start_drag)
        self.bind("<B1-Motion>", self.do_drag)
        self.bind("<ButtonRelease-1>", self.end_drag)
        self.bind("<Configure>", self.on_resize)

    def init_3d(self):
        """Initialize trimesh scene for 3D rendering"""
        try:
            # Load 3D Model
            if not os.path.exists("USBC_key_v2.glb"):
                print("GLB file not found, using 2D fallback")
                self.use_3d = False
                return

            # Load GLB using trimesh
            self.usb_scene = trimesh.load("USBC_key_v2.glb")
            print(f"Loaded GLB. Extents: {self.usb_scene.extents}")
            
            # Set camera to ensure visibility
            # Z-up model? Extents [1.07, 1.00, 4.79] implies long Z axis?
            # Or Y-up?
            # Calculate optimal camera distance
            max_extent = np.max(self.usb_scene.extents)
            self.base_distance = max_extent
            print(f"Base Distance: {self.base_distance}")
            
            # Try a standard view
            self.usb_scene.set_camera(distance=self.base_distance * self.zoom_current, center=[0,0,0], angles=[0, 0, 0])
            

            # Store original transforms for rotation
            self.original_transforms = {}
            for name in self.usb_scene.graph.nodes:
                try:
                    transform, _ = self.usb_scene.graph.get(name)
                    self.original_transforms[name] = transform.copy()
                except:
                    pass
            
            # Fix Z-Near to allow closer zoom (prevent clipping)
            if self.usb_scene.camera:
                self.usb_scene.camera.z_near = 0.1
                
            self.use_3d = True
            print("3D rendering initialized successfully!")
            
        except Exception as e:
            print(f"3D Init Error: {e}. Falling back to 2D.")
            self.use_3d = False

    def get_3d_render(self):
        """Render the 3D scene using persistent viewer. Returns PIL Image or None."""
        if not self.use_3d or self.usb_scene is None:
            return None
            
        try:
            import pyglet
            # Initialize viewer if needed
            if not hasattr(self, 'viewer') or self.viewer is None:
                from trimesh.viewer.windowed import SceneViewer
                # Create visible window (to force rendering) but position offscreen
                # Use TOOL style to hide from Taskbar
                self.viewer = SceneViewer(self.usb_scene, 
                                          resolution=(400, 200),
                                          start_loop=False, 
                                          visible=True,
                                          style=pyglet.window.Window.WINDOW_STYLE_TOOL)
                                          
                # Position offscreen
                self.viewer.set_location(10000, 10000)
            
                # Position offscreen
                self.viewer.set_location(10000, 10000)
            
            # --- Camera Orbit Logic ---
            # Rotate camera around the model centroid instead of rotating geometry
            # This ensures smooth pivoting and avoids breaking the scene graph
            theta_x = np.radians(self.rotate_x)
            theta_y = np.radians(self.rotate_y)
            
            # angles=[pitch, yaw, roll]
            self.usb_scene.set_camera(angles=[theta_x, theta_y, 0], 
                                      distance=self.base_distance * self.zoom_current, 
                                      center=self.usb_scene.centroid)
            # --------------------------

            # Force Draw
            self.viewer.switch_to() # Make context current
            self.viewer.dispatch_events()
            self.viewer.on_draw()
            
            # Capture
            image_data = pyglet.image.get_buffer_manager().get_color_buffer().get_image_data()
            # Convert to PIL
            # formatted = image_data.get_data('RGBA', image_data.width * 4) # bytes
            # img = Image.frombytes("RGBA", (image_data.width, image_data.height), formatted)
            
            # Trimesh has utility? No, use pyglet direct
            # Pyglet < 2.0 vs > 2.0?
            # image_data.get_data() returns bytes?
            # image_data.pitch ...
            
            # Robust way:
            import io
            buff = io.BytesIO()
            image_data.save(file=buff, encoder=None) # Save as PNG? No encoder defaults?
            # Pyglet save requires encoders.
            # Fallback: simple access
            
            raw_data = image_data.get_data("RGBA", image_data.width * 4)
            img = Image.frombytes("RGBA", (image_data.width, image_data.height), raw_data)
            
            # Flip since OpenGL is bottom-left origin
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            
            # Reset transforms for next frame
            for name, transform in self.original_transforms.items():
                self.usb_scene.graph.update(name, matrix=transform)

            # Raw image is already correct size (400x200)
            return img
            
        except Exception as e:
            print(f"Persistent Render Error: {e}")
            try:
                with open("error.log", "w") as f:
                    f.write(f"Persistent Render Error: {e}\n")
                    import traceback
                    traceback.print_exc(file=f)
            except: pass
            
            self.use_3d = False
            if hasattr(self, 'viewer') and self.viewer:
                try: self.viewer.close()
                except: pass
                self.viewer = None
            return None

    def create_radial_gradient_shadow(self, width, height):
        """Create a radial gradient shadow: Dark center fading to transparent"""
        scale = 2
        w, h = width * scale, height * scale
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        cx, cy = w // 2, h // 2
        pixels = img.load()
        for y in range(h):
            for x in range(w):
                dx = (x - cx) / cx if cx > 0 else 0
                dy = (y - cy) / (cy * 0.5) if cy > 0 else 0
                dist = math.sqrt(dx**2 + dy**2)
                if dist < 1.0:
                    # Power falloff for smoother fade
                    alpha = int(255 * 0.45 * (1.0 - dist**1.5))
                    pixels[x, y] = (0, 0, 0, alpha)
        return img.resize((width, height), Image.Resampling.LANCZOS)

    def on_resize(self, event):
        self.cx = event.width // 2
        self.cy = event.height // 2
        self.card_w = event.width
        self.card_h = event.height
        self.draw_scene()

    def get_scaled_shadow(self):
        """Scale the shadow based on rotation to simulate depth/perspective"""
        # Calculate scale factors based on rotation
        # When tilted, shadow should shrink on the axis of tilt
        scale_x = 1.0 - abs(self.rotate_y) / 90.0 * 0.3  # Shrink up to 30% on X
        scale_y = 1.0 - abs(self.rotate_x) / 90.0 * 0.3  # Shrink up to 30% on Y
        
        # Clamp
        scale_x = max(0.5, min(1.0, scale_x))
        scale_y = max(0.5, min(1.0, scale_y))
        
        # Scale the shadow
        new_w = int(self.shadow_base.width * scale_x)
        new_h = int(self.shadow_base.height * scale_y)
        
        if new_w < 10: new_w = 10
        if new_h < 10: new_h = 10
        
        return self.shadow_base.resize((new_w, new_h), Image.Resampling.LANCZOS)

    def draw_scene(self):
        print(f"Entering draw_scene. CX: {self.cx}")
        self.delete("all")
        
        # 1. Shadow (Scales based on rotation - stays centered, no movement)
        scaled_shadow = self.get_scaled_shadow()
        shadow_x = self.cx
        shadow_y = self.cy + 65  # Fixed position below USB key
        self.shadow_photo = ImageTk.PhotoImage(scaled_shadow)
        self.create_image(shadow_x, shadow_y, image=self.shadow_photo)
        
        # 2. Main Object (3D or 2D Fallback with perspective)
        img_to_draw = self.get_3d_render()
        if img_to_draw: print("Got 3D render successfully")
        else: print("3D render returned None")
        
        if not img_to_draw and self.usb_img_2d:
            # Fallback to 2D image with perspective simulation
            img_to_draw = self.apply_2d_perspective(self.usb_img_2d)

        if img_to_draw:
            usb_y = self.cy - 20  # Fixed position, no bobbing
            self.photo_image = ImageTk.PhotoImage(img_to_draw)
            self.create_image(self.cx, usb_y, image=self.photo_image)
        else:
            self.create_text(self.cx, self.cy, text="No USB Model/Image", font=APP_FONT_BOLD, fill="gray")

    def apply_2d_perspective(self, img):
        """Apply simple 2D perspective transform to simulate 3D pivoting"""
        if abs(self.rotate_y) < 0.5 and abs(self.rotate_x) < 0.5:
            return img
        
        w, h = img.size
        
        # Simulate Y-axis rotation (left/right tilt) by shrinking one side
        perspective_y = self.rotate_y / 45.0  # Normalize
        perspective_y = max(-0.9, min(0.9, perspective_y))
        
        # Simulate X-axis rotation (up/down tilt) by shrinking top or bottom
        perspective_x = self.rotate_x / 45.0
        perspective_x = max(-0.9, min(0.9, perspective_x))
        
        # Calculate corner offsets for perspective
        shrink_y = int(h * abs(perspective_y) * 0.15)  # Vertical shrink amount
        shrink_x = int(h * abs(perspective_x) * 0.15)  # Horizontal shrink amount
        
        # Define corners: top-left, top-right, bottom-right, bottom-left
        if perspective_y > 0:
            # Rotating right: right side goes back (shrinks)
            coeffs = self._find_coeffs(
                [(0, 0), (w, shrink_y), (w, h - shrink_y), (0, h)],  # destination
                [(0, 0), (w, 0), (w, h), (0, h)]  # source
            )
        else:
            # Rotating left: left side goes back (shrinks)
            coeffs = self._find_coeffs(
                [(0, shrink_y), (w, 0), (w, h), (0, h - shrink_y)],
                [(0, 0), (w, 0), (w, h), (0, h)]
            )
        
        try:
            return img.transform((w, h), Image.Transform.PERSPECTIVE, coeffs, Image.Resampling.BICUBIC)
        except:
            return img
    
    def _find_coeffs(self, target_coords, source_coords):
        """Calculate perspective transform coefficients"""
        import numpy as np
        matrix = []
        for s, t in zip(source_coords, target_coords):
            matrix.append([t[0], t[1], 1, 0, 0, 0, -s[0]*t[0], -s[0]*t[1]])
            matrix.append([0, 0, 0, t[0], t[1], 1, -s[1]*t[0], -s[1]*t[1]])
        A = np.array(matrix, dtype=np.float64)
        B = np.array([s[0] for s in source_coords] + [s[1] for s in source_coords], dtype=np.float64)
        res = np.linalg.lstsq(A, B, rcond=None)[0]
        return tuple(res)

    def start_drag(self, event):
        self.dragging = True
        self.start_x = event.x
        self.start_y = event.y
        self.saved_rotate_x = self.rotate_x
        self.saved_rotate_y = self.rotate_y
        
        # Zoom Out (shrink) on click (Further away)
        self.zoom_target = 1.3 
        self.animate_loop()

    def do_drag(self, event):
        if self.dragging:
            dx = event.x - self.start_x
            dy = event.y - self.start_y
            
            # Update rotation relative to start
            new_y = self.saved_rotate_y + dx * 0.5
            new_x = self.saved_rotate_x + dy * 0.5 
            
            # Clamp to prevent extreme rotation (User Request)
            # Tighten limits to keep front-facing
            # Default X: -90. Range: [-135, -45] (+/- 45)
            # Default Y: 90. Range: [45, 135] (+/- 45)
            self.rotate_y = max(45, min(135, new_y))
            self.rotate_x = max(-135, min(-45, new_x)) 
            
            self.draw_scene()

    def end_drag(self, event):
        self.dragging = False
        # Zoom In (grow) on release (Closer)
        self.zoom_target = 1.1 
        self.animate_loop()

    def animate_loop(self):
        needs_update = False
        
        # 1. Recoil Logic (Only if not dragging)
        if not self.dragging:
            target_x, target_y = -90.0, 90.0
            diff_x = self.rotate_x - target_x
            diff_y = self.rotate_y - target_y
            
            # Interpolate if far enough
            if abs(diff_x) > 0.1 or abs(diff_y) > 0.1:
                self.rotate_x = target_x + diff_x * 0.80
                self.rotate_y = target_y + diff_y * 0.80
                needs_update = True
            else:
                self.rotate_x = target_x
                self.rotate_y = target_y
        
        # 2. Zoom Logic
        if abs(self.zoom_current - self.zoom_target) > 0.001:
            diff = self.zoom_target - self.zoom_current
            self.zoom_current += diff * 0.2
            needs_update = True
        else:
            self.zoom_current = self.zoom_target
            
        if needs_update:
            self.draw_scene()
            self.after(16, self.animate_loop)

# --- WELCOME SCREEN ---
class WelcomeScreen(tk.Frame):
    def __init__(self, parent, on_continue):
        super().__init__(parent, bg="black")
        self.on_continue = on_continue
        self.place(relwidth=1, relheight=1)
        
        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Load Assets
        self.logo_img = None
        self.btn_img_normal = self.create_btn_img("white", "black")
        self.btn_img_hover = self.create_btn_img("#e0e0e0", "black")
        
        if os.path.exists("zentap_logo.png"):
            raw = Image.open("zentap_logo.png").resize((200, 200), Image.Resampling.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(raw)

        # Animated Ring State
        self.ring_r = 100
        self.ring_alpha = 255.0
        
        # Initial Draw & Bind
        self.bind("<Configure>", self.on_resize)
        self.animate_ring()

    def on_resize(self, event):
        w, h = event.width, event.height
        cx, cy = w // 2, h // 2
        
        self.canvas.delete("all")
        
        # Logo placeholder (Animation handles ring/logo drawing)
        # We just need to store cx, cy for animation to use
        self.cx = cx
        self.cy = max(cy - 50, 150) # Shift up slightly
        
        # Text
        self.canvas.create_text(self.cx, self.cy + 150, text="ZEN TAP", font=("Roboto Medium", 32), fill="white", tags="text")
        self.canvas.create_text(self.cx, self.cy + 190, text="— FOCUS • TAP • ACHIEVE —", font=("Roboto", 10), fill="gray", tags="text")
        self.canvas.create_text(self.cx, self.cy + 220, text="1.0.1 ZEN OS", font=("Roboto", 8), fill="#444", tags="text")
        
        # Button
        btn_y = h - 100
        self.btn_id = self.canvas.create_image(self.cx, btn_y, image=self.btn_img_normal, tags="btn")
        
        self.canvas.tag_bind("btn", "<Enter>", lambda e: self.canvas.itemconfig(self.btn_id, image=self.btn_img_hover))
        self.canvas.tag_bind("btn", "<Leave>", lambda e: self.canvas.itemconfig(self.btn_id, image=self.btn_img_normal))
        self.canvas.tag_bind("btn", "<Button-1>", lambda e: [self.on_continue(), self.destroy()])

    def create_btn_img(self, bg, fg):
        w, h = 300, 60
        scale = 4
        img = Image.new("RGBA", (w*scale, h*scale), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        radius = 20*scale
        draw.rounded_rectangle((0,0, w*scale, h*scale), radius, fill=bg)
        try: font = ImageFont.truetype("arialbd.ttf", 16*scale)
        except: font = ImageFont.load_default()
        
        text = "Continue  →"
        bbox = draw.textbbox((0,0), text, font=font)
        tx = (w*scale - (bbox[2]-bbox[0]))//2
        ty = (h*scale - (bbox[3]-bbox[1]))//2 - 4*scale
        draw.text((tx, ty), text, fill=fg, font=font)
        return ImageTk.PhotoImage(img.resize((w,h), Image.Resampling.LANCZOS))

    def animate_ring(self):
        if not self.winfo_exists(): return
        
        # Use stored center if available, else default
        cx = getattr(self, 'cx', self.winfo_width()//2)
        cy = getattr(self, 'cy', self.winfo_height()//2 - 50)
        
        self.canvas.delete("ring")
        self.canvas.delete("logo")
        
        gray = int(max(0, min(128, self.ring_alpha)))
        color = f"#{gray:02x}{gray:02x}{gray:02x}"
        
        if gray > 10:
            self.canvas.create_oval(cx-self.ring_r, cy-self.ring_r, cx+self.ring_r, cy+self.ring_r, outline=color, width=1, tags="ring")
            
        if self.logo_img:
            self.canvas.create_image(cx, cy, image=self.logo_img, tags="logo")
            
        self.ring_r += 0.8
        self.ring_alpha -= 3.0
        if self.ring_r > 130:
            self.ring_r = 100
            self.ring_alpha = 128.0
            
        self.after(16, self.animate_ring)

# --- MAIN APP ---
class ZenTapApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ZenTap For Windows")
        self.root.geometry("1100x850")
        self.root.configure(bg="black")
        
        # Load Resources
        self.load_resources()
        
        # State
        self.is_active = False
        self.all_apps = []
        self.web_keywords = []    
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Show Welcome Screen first
        self.welcome_screen = WelcomeScreen(self.root, self.init_dashboard)
        
    def load_resources(self):
        self.photo_icon = None
        self.missing_icon_img = None
        self.edit_icon_img = None
        
        # Win Icon
        if os.path.exists("z_icon.png"):
            icon = Image.open("z_icon.png")
            self.photo_icon = ImageTk.PhotoImage(icon)
            self.root.iconphoto(False, self.photo_icon)
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('zentap.desktop')
            
        # Fallback Icon
        if os.path.exists("missing_icon.png"):
            raw = Image.open("missing_icon.png").resize((48, 48), Image.Resampling.LANCZOS)
            self.missing_icon_img = ImageTk.PhotoImage(raw)
            
        # Create Edit Icon (Pencil)
        img = Image.new("RGBA", (24, 24), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        # Simple pencil shape
        draw.line((4, 20, 8, 20, 20, 8, 16, 4, 4, 16, 4, 20), fill="black", width=2)
        self.edit_icon_img = ImageTk.PhotoImage(img)

    def init_dashboard(self):
        self.root.configure(bg="white")
        
        # Main Container for Centering
        self.main_container = tk.Frame(self.root, bg="white")
        self.main_container.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Use pack with expand for flexible spacing
        self.content_frame = tk.Frame(self.main_container, bg="white")
        self.content_frame.pack(expand=True, fill="both") # Changed from place to pack
        
        self.popup = None # Popup tracker
        
        # --- HEADER ---
        header = tk.Frame(self.content_frame, bg="white")
        header.pack(fill="x", pady=(0, 20), expand=True) # expand=True to push spacing
        
        tk.Label(header, text="ZenTap for Desktop", font=APP_FONT_BOLD, bg="white").pack(side="left")
        
        # Settings Button - composite image (gear on square)
        self.settings_btn = tk.Label(header, bg="white", cursor="hand2")
        self.settings_btn.pack(side="right")
        
        try:
            square = Image.open("settings_square.png").resize((36, 36), Image.Resampling.LANCZOS)
            gear = Image.open("settings_gear.png").resize((24, 24), Image.Resampling.LANCZOS)
            # Center gear on square
            square.paste(gear, (6, 6), gear if gear.mode == 'RGBA' else None)
            self.settings_icon = ImageTk.PhotoImage(square)
            self.settings_btn.config(image=self.settings_icon)
        except:
            self.settings_btn.config(text="⚙", font=("Segoe UI Symbol", 18))
        
        self.settings_btn.bind("<Button-1>", lambda e: self.show_settings_menu())
        self.settings_menu = None  # Track open menu
        
        # --- CARD ---
        self.card = InteractiveCard(self.content_frame, width=600, height=300, bg="white")
        self.card.pack(expand=True) # expand=True
        
        # --- ZEN BUTTON ---
        self.zen_btn = tk.Canvas(self.content_frame, width=400, height=80, bg="white", highlightthickness=0)
        self.zen_btn.pack(pady=10, expand=True) # expand=True
        self._draw_main_btn("black", "Zen Device")
        self.zen_btn.bind("<Button-1>", lambda e: self.toggle_zen())
        self.zen_btn.bind("<Enter>", lambda e: self.zen_btn.config(cursor="hand2"))
        self.zen_btn.bind("<Leave>", lambda e: self.zen_btn.config(cursor=""))
        
        # --- STATS ROW ---
        stats_frame = tk.Frame(self.content_frame, bg="white")
        stats_frame.pack(fill="x", pady=30, expand=True) # expand=True
        
        def create_stat(parent, icon_img, val, label):
            c = tk.Canvas(parent, width=150, height=80, bg="white", highlightthickness=0)
            c.pack(side="left", padx=10, expand=True) 
            
            # Rounded Border
            r=20; w=150; h=80
            c.create_arc(0, 0, r*2, r*2, start=90, extent=90, style="arc", outline="black"); 
            c.create_arc(w-r*2, 0, w, r*2, start=0, extent=90, style="arc", outline="black")
            c.create_arc(w-r*2, h-r*2, w, h, start=270, extent=90, style="arc", outline="black")
            c.create_arc(0, h-r*2, r*2, h, start=180, extent=90, style="arc", outline="black")
            c.create_line(r,0, w-r,0, fill="black"); c.create_line(r,h, w-r,h, fill="black")
            c.create_line(0,r, 0,h-r, fill="black"); c.create_line(w,r, w,h-r, fill="black")
            
            c.create_text(30, 40, text=icon_img, font=("Segoe UI Emoji", 20))
            c.create_text(60, 28, text=val, font=("Roboto", 14, "bold"), anchor="nw", fill="black")
            c.create_text(60, 50, text=label, font=("Roboto", 10), anchor="nw", fill="#666")

        create_stat(stats_frame, "🕒", "0m", "Time")
        create_stat(stats_frame, "🔥", "4", "Streak")
        create_stat(stats_frame, "🏆", "0", "Sessions")
        
        # --- READY TO BLOCK ---
        self.block_frame = tk.Frame(self.content_frame, bg="white")
        self.block_frame.pack(fill="x", pady=(20, 10), expand=True) # expand=True
        tk.Label(self.block_frame, text="Ready To Block:", font=("Roboto Medium", 14), bg="white").pack(anchor="w")
        
        # Responsive container for list - add bottom padding to move bar down
        self.slot_canvas = tk.Canvas(self.block_frame, height=100, bg="white", highlightthickness=0)
        self.slot_canvas.pack(fill="x", expand=True, pady=(15, 25))
        self.slot_canvas.bind("<Button-1>", self.open_block_summary)
        self.slot_canvas.bind("<Configure>", lambda e: self.update_slots())
        
        # Backend
        threading.Thread(target=self.load_apps_background, daemon=True).start()

    def _draw_main_btn(self, color, text):
        self.zen_btn.delete("all")
        
        # Dimensions matching the canvas size/layout
        w, h = 400, 80
        btn_w, btn_h = 300, 60
        scale = 8 # Ultra High Res
        
        # Cache key based on color/text
        cache_key = f"btn_{color}_{text}"
        if not hasattr(self, '_btn_cache'): self._btn_cache = {}
        
        if cache_key not in self._btn_cache:
            # Create high-res image
            full_w, full_h = w * scale, h * scale
            img = Image.new("RGBA", (full_w, full_h), (0,0,0,0))
            draw = ImageDraw.Draw(img)
            
            # Center coordinates
            cx, cy = full_w // 2, full_h // 2
            bw, bh = btn_w * scale, btn_h * scale
            
            # Shadow
            shadow_offset = 6 * scale
            shadow_color = (200, 200, 200, 100) # Soft gray shadow
            x1 = cx - bw // 2
            y1 = cy - bh // 2
            x2 = cx + bw // 2
            y2 = cy + bh // 2
            
            # Draw Shadow (Offset)
            draw.rounded_rectangle(
                (x1, y1 + shadow_offset, x2, y2 + shadow_offset),
                radius=bh//2, fill=shadow_color
            )
            
            # Draw Button Body
            check_col = color.lower()
            fill_col = "#000000" if "black" in check_col else color
            outline_col = fill_col
            
            draw.rounded_rectangle(
                (x1, y1, x2, y2),
                radius=bh//2, fill=fill_col, outline=outline_col
            )
            
            # Text
            try:
                font_size = 20 * scale
                font = ImageFont.truetype("arialbd.ttf", font_size)
            except:
                font = ImageFont.load_default()
            
            # Draw text
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]
            draw.text((cx - text_w // 2, cy - text_h // 2 - (scale*2)), text, fill="white", font=font)
            
            # Resize
            img = img.resize((w, h), Image.Resampling.LANCZOS)
            self._btn_cache[cache_key] = ImageTk.PhotoImage(img)
            
        # Draw cached image
        self.zen_btn.create_image(w//2, h//2, image=self._btn_cache[cache_key])

    def update_slots(self):
        self.slot_canvas.delete("all")
        selected = [a for a in self.all_apps if a['checked']]
        
        # Dashboard wants "8 small squares"
        # If user selects more than 8, we likely show the first 8 or the last 8?
        # User said "15 max" for selection, but "bottom bar should have 8 small squares".
        # We will show the first 8.
        
    def update_slots(self):
        self.slot_canvas.delete("all")
        # Sort apps by timestamp (default 0 if missing)
        selected_apps = sorted([a for a in self.all_apps if a['checked']], key=lambda x: x.get('selection_ts', 0))
        
        # Convert web_keywords (strings) to dicts with icons for unified handling
        selected_websites = []
        for item in self.web_keywords:
            if isinstance(item, dict):
                selected_websites.append(item)
            else:
                # Legacy string format - convert to dict
                selected_websites.append({'keyword': item, 'icon': None, 'icon_pil': None})
        
        # Combine: apps first, then websites
        combined = []
        for app in selected_apps:
            combined.append({'type': 'app', 'name': app.get('name', '?'), 'icon': app.get('icon'), 'icon_pil': app.get('icon_pil')})
        for web in selected_websites:
            combined.append({'type': 'web', 'name': web.get('keyword', '?'), 'icon': web.get('icon'), 'icon_pil': web.get('icon_pil')})
        
        # Responsive sizing
        canvas_w = self.slot_canvas.winfo_width()
        canvas_h = max(80, self.slot_canvas.winfo_height()) # Enforce min height
        if canvas_w < 100: canvas_w = 600
        
        num_slots = 8
        
        # Dynamic slot size: scale with window
        base_w = 800 # Reference width
        ratio = max(0.8, canvas_w / base_w) # Don't shrink too much
        
        # Calculate max possible size based on height
        max_h = canvas_h - 24 # 12px padding top/bottom
        
        slot_size = int(55 * ratio)
        slot_size = max(45, min(120, min(slot_size, max_h))) # Clamp to fits in height
        
        gap = int(12 * ratio)        # Gap scales too
        
        # Slot corner radius - about 24% of slot size for nice rounded look
        r = int(slot_size * 0.24)
        
        # Center the block
        total_w = num_slots * slot_size + (num_slots + 1) * gap
        start_x = (canvas_w - total_w) // 2
        
        # Vertical center
        y = canvas_h // 2  # Center point
        
        # Dock bounds - slightly larger than slots, but clamped to canvas
        dock_x1 = start_x - 5
        dock_x2 = start_x + total_w + 5
        dock_y1 = max(2, y - slot_size//2 - 10)
        dock_y2 = min(canvas_h - 2, y + slot_size//2 + 10)
        
        # Draw Dock - corner radius proportional to dock height
        dock_r = min(18, (dock_y2 - dock_y1) // 4)
        # Convert dock coords to width/height for image generation
        d_w = dock_x2 - dock_x1
        d_h = dock_y2 - dock_y1
        
        dock_key = f"dock_{d_w}_{d_h}_{dock_r}"
        if not hasattr(self, 'dock_cache'): self.dock_cache = {}
        if dock_key not in self.dock_cache:
            self.dock_cache[dock_key] = self.create_smooth_rounded_rect(d_w, d_h, dock_r, "white", "black", width=2)
            
        # Draw image centered
        self.slot_canvas.create_image(dock_x1 + d_w/2, dock_y1 + d_h/2, image=self.dock_cache[dock_key])

        # Keep reference to new icons to prevent GC
        self.current_slot_icons = []

        for i in range(num_slots):
            # Centered positioning
            x = start_x + (gap * (i+1)) + (slot_size * i) + (slot_size/2)
            
            x1 = x - slot_size//2
            y1 = y - slot_size//2
            x2 = x + slot_size//2
            y2 = y + slot_size//2
            
            # Draw empty slot (rounded rect) - Inner squares
            bg_col = "" # Transparent/White
            out_col = "black" # Solid black outline
            
            is_overflow = False
            overflow_count = 0
            
            if len(combined) > 8 and i == 7:
                is_overflow = True
                overflow_count = len(combined) - 7
                bg_col = "#ccc" 
                out_col = "black" 
            
            # Create Image for slot background if not cached
            slot_key = f"{slot_size}_{r}_{bg_col}_{out_col}"
            if not hasattr(self, 'slot_bg_cache'): self.slot_bg_cache = {}
            
            if slot_key not in self.slot_bg_cache:
                self.slot_bg_cache[slot_key] = self.create_smooth_rounded_rect(slot_size, slot_size, r, bg_col, out_col)
            
            # Draw slot background image
            if bg_col or out_col:
                self.slot_canvas.create_image(x, y, image=self.slot_bg_cache[slot_key])
            
            if is_overflow:
                self.slot_canvas.create_text(x, y, text=f"+{overflow_count}", font=("Roboto", 18, "bold"), fill="#333")
            elif i < len(combined):
                 # Normal slot (app or website)
                 item = combined[i]
                 
                 # Dynamic Icon Resizing
                 if item.get('icon_pil'):
                     try:
                         # Resize to fit slot (minus padding) - made bigger
                         s = int(slot_size * 0.85)
                         resized = item['icon_pil'].resize((s, s), Image.Resampling.LANCZOS)
                         new_icon = ImageTk.PhotoImage(resized)
                         self.current_slot_icons.append(new_icon) # Keep Ref
                         self.slot_canvas.create_image(x, y, image=new_icon)
                     except:
                         pass
                 elif item.get('icon'):
                      self.slot_canvas.create_image(x, y, image=item['icon'])
                 else:
                      # Missing icon fallback - use missing_icon for websites, letter for apps
                      if item.get('type') == 'web' and self.missing_icon_img:
                          self.slot_canvas.create_image(x, y, image=self.missing_icon_img)
                      else:
                          self.slot_canvas.create_text(x, y, text=item['name'][0].upper(), font=("Roboto", 14, "bold"), fill="#666")
    

            
    def create_smooth_rounded_rect(self, w, h, r, fill, outline, width=1):
        """Create a high-quality anti-aliased rounded rectangle image"""
        scale = 8 # Ultra High Res for everything
        # Padding to avoid clipping thick borders
        pad = 2 * scale
        
        # Create larger image for supersampling
        img = Image.new("RGBA", (w*scale + 2*pad, h*scale + 2*pad), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        
        # Handle empty strings as None for PIL
        if fill == "": fill = None
        if outline == "": outline = None
        
        # Draw rounded rect
        draw.rounded_rectangle(
            (pad, pad, w*scale + pad, h*scale + pad), 
            radius=r*scale, 
            fill=fill, 
            outline=outline, 
            width=width*scale
        )
        
        # Resize down with high quality filter
        img = img.resize((w + 2, h + 2), Image.Resampling.LANCZOS)
        
        return ImageTk.PhotoImage(img)

    def create_smooth_circle(self, d, fill, outline, width=1):
        """Create a high-quality anti-aliased circle image"""
        # A circle is just a rounded rect with radius = d/2
        return self.create_smooth_rounded_rect(d, d, d//2, fill, outline, width)

    def draw_rounded_rect_canvas(self, c, x1, y1, x2, y2, r, fill, outline):
        # Legacy fallback if needed, but we should use images now
        pass


        



    # --- POPUPS ---
    # --- POPUPS ---
    def open_block_summary(self, e):
        # Prevent multiple instances
        if self.popup and self.popup.win.winfo_exists():
            self.popup.win.lift()
            self.popup.win.focus_force()
            return
            
        self.popup = ManageAppsWindow(self.root, self.all_apps, self.web_keywords, self.update_slots, self.show_hud)
        

    # --- LOGIC ---
    def load_apps_background(self):
        if USE_SHORTCUT_RESOLVER: pythoncom.CoInitialize()
        paths = [os.path.join(os.environ.get("ProgramData", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
                 os.path.join(os.environ.get("AppData", ""), "Microsoft", "Windows", "Start Menu", "Programs")]
        temp = {}
        for p in paths:
            if os.path.exists(p):
                for r, _, f in os.walk(p):
                    for file in f:
                        if file.endswith(".lnk") and not "uninstall" in file.lower():
                            temp[file[:-4]] = os.path.join(r, file)
        
        for name in sorted(temp.keys()):
            self.all_apps.append({'name': name, 'path': temp[name], 'checked': False, 'icon': None})
            
        self.root.after(0, self.update_slots)
        
        for app in self.all_apps:
            try:
                rp = resolve_shortcut(app['path'])
                img = get_file_icon(rp)
                if not img: img = get_file_icon(app['path'])
                
                if img:
                    app['icon_pil'] = img # Store original for resizing
                    app['icon'] = ImageTk.PhotoImage(img)
                elif self.missing_icon_img:
                    app['icon'] = self.missing_icon_img
                else:
                    # Letter fallback
                    i = Image.new("RGBA", (48,48), "#ddd")
                    d = ImageDraw.Draw(i)
                    d.ellipse((0,0,48,48), fill="#999")
                    app['icon'] = ImageTk.PhotoImage(i)
            except: pass
            if self.all_apps.index(app) % 5 == 0:
                self.root.after(0, self.update_slots)
        self.root.after(0, self.update_slots)

    # --- BLOCKING & HUD ---
    def toggle_zen(self):
        if not self.is_active:
            sel = [a for a in self.all_apps if a['checked']]
            if not sel and not self.web_keywords: 
                messagebox.showwarning("ZenTap", "Select apps or add website keywords first."); return
            
            # Check for running apps
            running = []
            procs = {p.info['name'].lower() for p in psutil.process_iter(['name'])}
            for app in sel:
                target = APP_MAP.get(app['name'], app['name'].lower().replace(" ","")+".exe").lower()
                if target in procs:
                    running.append(app['name'])
            
            if running:
                msg = "The following apps are currently running and will be closed and blocked:\n\n" + "\n".join(f"• {a}" for a in running) + "\n\nDo you want to proceed?"
                if not messagebox.askokcancel("ZenTap Warning", msg):
                    return

            self.is_active = True
            self._draw_main_btn("black", "Un-Zen Device") # Remains black
            self.trigger_pulse()
            threading.Thread(target=self.loop, args=(sel,), daemon=True).start()
        else:
            self.is_active = False
            self._draw_main_btn("black", "Zen Device")



    def _draw_gear_icon(self, rotation=0):
        """Draw a gear icon using settings_gear.png with rotation"""
        self.settings_canvas.delete("all")
        
        try:
            # Load and rotate the gear image
            gear_img = Image.open("settings_gear.png").resize((28, 28), Image.Resampling.LANCZOS)
            rotated = gear_img.rotate(-rotation, resample=Image.Resampling.BICUBIC, expand=False)
            self.gear_photo = ImageTk.PhotoImage(rotated)
            self.settings_canvas.create_image(18, 18, image=self.gear_photo)
        except Exception as e:
            # Fallback to Canvas-drawn gear if image not found
            import math
            cx, cy = 18, 18
            outer_r = 14
            inner_r = 8
            teeth = 8
            rot_rad = math.radians(rotation)
            
            points = []
            for i in range(teeth * 2):
                angle = rot_rad + (math.pi * 2 * i) / (teeth * 2)
                r = outer_r if i % 2 == 0 else inner_r + 2
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
                points.extend([x, y])
            
            self.settings_canvas.create_polygon(points, fill="black", outline="black", smooth=False)
            self.settings_canvas.create_oval(cx-5, cy-5, cx+5, cy+5, fill="white", outline="white")
    
    def _animate_gear_rotation(self, target_rotation, steps_remaining=6):
        """Animate gear rotation smoothly"""
        if steps_remaining <= 0:
            self.gear_rotation = target_rotation % 360
            self._draw_gear_icon(self.gear_rotation)
            return
        
        # Calculate current step
        step_size = (target_rotation - self.gear_rotation) / steps_remaining
        self.gear_rotation += step_size
        self._draw_gear_icon(self.gear_rotation)
        
        # Schedule next step
        self.root.after(25, lambda: self._animate_gear_rotation(target_rotation, steps_remaining - 1))

    def show_settings_menu(self):
        # Toggle menu - if open, close it
        if self.settings_menu:
            try:
                if self.settings_menu.winfo_exists():
                    self._close_settings_menu()
                    return
            except:
                pass
            self.settings_menu = None
        
        # Create dropdown menu popup with rounded corners
        self.settings_menu = tk.Toplevel(self.root)
        self.settings_menu.overrideredirect(True)
        self.settings_menu.attributes("-topmost", True)
        
        # Use transparent color for rounded corners effect
        menu_w, menu_h = 220, 205
        trans_color = "#f0f0f0"
        self.settings_menu.configure(bg=trans_color)
        self.settings_menu.wm_attributes("-transparentcolor", trans_color)
        
        # Position: right side aligned with settings icon, moved down a bit
        btn_right = self.settings_btn.winfo_rootx() + self.settings_btn.winfo_width()
        x = btn_right - menu_w
        y = self.settings_btn.winfo_rooty() + 45
        self.settings_menu.geometry(f"{menu_w}x{menu_h}+{x}+{y}")
        
        # Canvas for rounded rectangle background
        canvas = tk.Canvas(self.settings_menu, width=menu_w, height=menu_h, 
                          bg=trans_color, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        
        # Generate points for smooth rounded rectangle
        # Generate points for smooth rounded rectangle - Very High Resolution
        # High Quality Image Background
        try:
             self.popup_bg_img = self.create_smooth_rounded_rect(menu_w, menu_h, 12, "white", "#bbb", width=1)
             canvas.create_image(menu_w//2, menu_h//2, image=self.popup_bg_img)
        except Exception as e:
             # Fallback
             print(f"Error drawing popup: {e}")
             pass
        
        # Menu frame on top of canvas
        menu_frame = tk.Frame(canvas, bg="white")
        canvas.create_window(menu_w//2, menu_h//2, window=menu_frame, width=menu_w-10, height=menu_h-10)
        
        # Notification row (with toggle)
        notif_row = tk.Frame(menu_frame, bg="white", cursor="hand2")
        notif_row.pack(fill="x", padx=8, pady=(10, 8))
        
        # Bell icon
        self.bell_label = tk.Label(notif_row, text="🔔", font=("Segoe UI Emoji", 14), bg="white")
        self.bell_label.pack(side="left", padx=(0, 10))
        self._update_bell_label()
        
        # Text: Silence / Notifications
        notif_text_frame = tk.Frame(notif_row, bg="white")
        notif_text_frame.pack(side="left")
        tk.Label(notif_text_frame, text="Silence", font=("Roboto Medium", 10), bg="white", anchor="w", bd=0, pady=0).pack(fill="x", pady=0)
        tk.Label(notif_text_frame, text="Notifications", font=("Roboto Medium", 10), bg="white", anchor="w", bd=0, pady=0).pack(fill="x", pady=0)
        
        # Toggle switch
        self.toggle_canvas = tk.Canvas(notif_row, width=40, height=22, bg="white", highlightthickness=0)
        self.toggle_canvas.pack(side="right", padx=(0, 5))
        self._draw_pill_toggle(self.toggle_canvas, getattr(self, 'notifications_muted', False))
        
        def toggle_click(e=None):
            self._animate_toggle()
            return "break"
        
        notif_row.bind("<Button-1>", toggle_click)
        self.toggle_canvas.bind("<Button-1>", toggle_click)
        self.bell_label.bind("<Button-1>", toggle_click)
        for child in notif_text_frame.winfo_children():
            child.bind("<Button-1>", toggle_click)
        
        # Divider
        tk.Frame(menu_frame, height=1, bg="#e5e5e5").pack(fill="x", padx=8)
        
        # Founders row
        founders_row = tk.Frame(menu_frame, bg="white", cursor="hand2")
        founders_row.pack(fill="x", padx=8, pady=8)
        
        # Founders Icon
        try:
            founders_img = Image.open("founders_icon.png")
            founders_img.thumbnail((28, 28), Image.Resampling.LANCZOS)
            self.founders_icon = ImageTk.PhotoImage(founders_img)
            tk.Label(founders_row, image=self.founders_icon, bg="white").pack(side="left", padx=(0, 10))
        except:
             tk.Label(founders_row, text="👥", font=("Segoe UI Emoji", 14), bg="white").pack(side="left", padx=(0, 10))
             
        tk.Label(founders_row, text="Founders", font=("Roboto Medium", 11), bg="white").pack(side="left")
        founders_row.bind("<Button-1>", lambda e: self._menu_click(self.show_founders))
        for child in founders_row.winfo_children():
            child.bind("<Button-1>", lambda e: self._menu_click(self.show_founders))
        
        # Divider
        tk.Frame(menu_frame, height=1, bg="#e5e5e5").pack(fill="x", padx=8)
        
        # What's New row
        whats_row = tk.Frame(menu_frame, bg="white", cursor="hand2")
        whats_row.pack(fill="x", padx=8, pady=8)
        
        # What's New Icon
        try:
            whats_img = Image.open("whatsnew_icon.png")
            whats_img.thumbnail((28, 28), Image.Resampling.LANCZOS)
            self.whats_icon = ImageTk.PhotoImage(whats_img)
            tk.Label(whats_row, image=self.whats_icon, bg="white").pack(side="left", padx=(0, 10))
        except:
            tk.Label(whats_row, text="✨", font=("Segoe UI Emoji", 14), bg="white").pack(side="left", padx=(0, 10))
            
        tk.Label(whats_row, text="What's New", font=("Roboto Medium", 11), bg="white").pack(side="left")
        whats_row.bind("<Button-1>", lambda e: self._menu_click(self.show_whats_new))
        for child in whats_row.winfo_children():
            child.bind("<Button-1>", lambda e: self._menu_click(self.show_whats_new))
        
        # Divider
        tk.Frame(menu_frame, height=1, bg="#e5e5e5").pack(fill="x", padx=8)
        
        # Unpair USB Key row
        unpair_row = tk.Frame(menu_frame, bg="white", cursor="hand2")
        unpair_row.pack(fill="x", padx=8, pady=(8, 10))
        
        # Icon - load from unpair_usb.png (bigger size, 38x38)
        try:
            unpair_img = Image.open("unpair_usb.png")
            unpair_img.thumbnail((38, 38), Image.Resampling.LANCZOS)
            self.unpair_icon = ImageTk.PhotoImage(unpair_img)
            tk.Label(unpair_row, image=self.unpair_icon, bg="white").pack(side="left", padx=(0, 10))
        except:
            tk.Label(unpair_row, text="🔌", font=("Segoe UI Emoji", 16), bg="white").pack(side="left", padx=(0, 10))
        
        # Red text - aligned with others
        tk.Label(unpair_row, text="Unpair USB Key", font=("Roboto Medium", 11), bg="white", fg="#FF3B30").pack(side="left")
        
        # Red dot on right
        tk.Label(unpair_row, text="•", font=("SF Pro Display", 16, "bold"), bg="white", fg="#FF3B30").pack(side="right", padx=5)
        
        unpair_row.bind("<Button-1>", lambda e: self._menu_click(self.unpair_usb))
        for child in unpair_row.winfo_children():
            child.bind("<Button-1>", lambda e: self._menu_click(self.unpair_usb))
        
        # Close when clicking outside or app state changes
        def setup_bindings():
            self._menu_click_binding = self.root.bind("<Button-1>", self._check_menu_click, add="+")
            self._menu_unmap_binding = self.root.bind("<Unmap>", lambda e: self._close_settings_menu() if self.settings_menu else None, add="+")
            self._menu_configure_binding = self.root.bind("<Configure>", lambda e: self._close_settings_menu() if self.settings_menu else None, add="+")
            # Bind to root focus out to catch app switching
            self._root_focus_out_binding = self.root.bind("<FocusOut>", lambda e: self.root.after(50, self._check_focus_lost), add="+")

        self.root.after(200, setup_bindings)
        
        # Close when focus is lost (switching apps) - Bind to popup as well
        self.settings_menu.bind("<FocusOut>", lambda e: self.root.after(50, self._check_focus_lost))
    
    def _draw_rounded_rect_popup(self, canvas, w, h, r, border_color, fill_color):
        """Draw a rounded rectangle on canvas for popup background"""
        # Create rounded rectangle using polygon + arcs
        points = [
            r, 0,
            w-r, 0,
            w, 0,
            w, r,
            w, h-r,
            w, h,
            w-r, h,
            r, h,
            0, h,
            0, h-r,
            0, r,
            0, 0,
            r, 0
        ]
        # Draw filled background
        canvas.create_polygon(points, smooth=True, fill=fill_color, outline=border_color, width=1)
    
    def _menu_click(self, cmd):
        """Handle click on menu item"""
        self._close_settings_menu()
        cmd()
    
    def _check_focus_lost(self):
        """Check if focus was lost to another app"""
        if not self.settings_menu:
            return
        try:
            # If focus is None, it means another app has focus
            if self.root.focus_get() is None:
                self._close_settings_menu()
        except:
            pass
    
    def _check_menu_click(self, event):
        """Check if click is outside menu and close if so"""
        if not self.settings_menu:
            return
        try:
            if not self.settings_menu.winfo_exists():
                return
        except:
            return
        
        # Ignore clicks on settings button (it handles its own toggle)
        sx, sy = self.settings_btn.winfo_rootx(), self.settings_btn.winfo_rooty()
        sw, sh = self.settings_btn.winfo_width(), self.settings_btn.winfo_height()
        if sx <= event.x_root <= sx + sw and sy <= event.y_root <= sy + sh:
            return
        
        # Check if click is outside menu
        mx, my = self.settings_menu.winfo_rootx(), self.settings_menu.winfo_rooty()
        mw, mh = self.settings_menu.winfo_width(), self.settings_menu.winfo_height()
        if not (mx <= event.x_root <= mx + mw and my <= event.y_root <= my + mh):
            self._close_settings_menu()
    
    
    def _close_settings_menu(self):
        """Close the settings menu"""
        
        # Unbind click handler
        try:
            if hasattr(self, '_menu_click_binding'):
                self.root.unbind("<Button-1>", self._menu_click_binding)
                del self._menu_click_binding
        except:
            pass
        
        # Unbind configure handler
        try:
            if hasattr(self, '_menu_configure_binding'):
                self.root.unbind("<Configure>", self._menu_configure_binding)
                del self._menu_configure_binding
        except:
            pass
        
        # Unbind unmap handler
        try:
            if hasattr(self, '_menu_unmap_binding'):
                self.root.unbind("<Unmap>", self._menu_unmap_binding)
                del self._menu_unmap_binding
        except:
            pass
        
        # Unbind root focus out
        try:
            if hasattr(self, '_root_focus_out_binding'):
                self.root.unbind("<FocusOut>", self._root_focus_out_binding)
                del self._root_focus_out_binding
        except:
            pass

        if self.settings_menu:
            try:
                if self.settings_menu.winfo_exists():
                    self.settings_menu.destroy()
            except:
                pass
        self.settings_menu = None
    
    def _animate_toggle(self):
        """Animate the toggle switch smoothly"""
        # Toggle state
        self.notifications_muted = not getattr(self, 'notifications_muted', False)
        
        # Do smooth animation in 5 steps over 100ms
        steps = 5
        delay = 20  # ms per step
        
        def animate_step(step):
            if not hasattr(self, 'toggle_canvas') or not self.toggle_canvas.winfo_exists():
                return
            
            progress = step / steps
            if self.notifications_muted:
                # Animating from off to on (knob moves right)
                knob_x = int(2 + (40 - 22 - 2) * progress)
            else:
                # Animating from on to off (knob moves left)
                knob_x = int((40 - 22) - (40 - 22 - 2) * progress)
            
            self.toggle_canvas.delete("all")
            w, h = 40, 22
            
            # Background
            bg_color = "black" if self.notifications_muted else "#ccc"
            if step < steps:
                # Blend colors during animation
                bg_color = "#666" if step > steps//2 else "#999"
            
            # Draw pill background (HIGH RES IMAGE)
            if not hasattr(self, 'toggle_bg_imgs'): self.toggle_bg_imgs = {}
            k = f"{w}_{h}_{bg_color}"
            if k not in self.toggle_bg_imgs:
                self.toggle_bg_imgs[k] = self.create_smooth_rounded_rect(w, h, h//2, bg_color, None, 0)
            
            self.toggle_canvas.create_image(w//2, h//2, image=self.toggle_bg_imgs[k])
            
            # Draw knob (HIGH RES IMAGE)
            if not hasattr(self, 'toggle_knob_img'):
                # Size: h-4
                d = h-4
                self.toggle_knob_img = self.create_smooth_circle(d, "white", None, 0)
            
            # Knob position: center of the knob image
            # knob_x is top-left in oval coords, so add radius for center
            knob_radius = (h-4)//2
            img_center_x = knob_x + knob_radius
            img_center_y = 2 + knob_radius
            
            # Adjust for internal padding of component? create_smooth_circle returns a slightly padded component
            # create_smooth_rounded_rect adds 1px padding on all sides (resized from 2*scale pad)
            # So the image size is d+2. Center is at (d+2)/2.
            # We want to place it so top-left is at (knob_x, 2)
            # Canvas.create_image takes center coordinates by default?
            self.toggle_canvas.create_image(img_center_x + 1, img_center_y + 1, image=self.toggle_knob_img)
            
            if step < steps:
                self.root.after(delay, lambda: animate_step(step + 1))
            else:
                # Final state
                self._draw_pill_toggle(self.toggle_canvas, self.notifications_muted)
                self._update_bell_label()
                # Actually toggle notifications in background
                self._do_toggle_notifications()
        
        animate_step(0)
    
    def _do_toggle_notifications(self):
        """Toggle Windows notifications in background thread"""
        import threading
        def toggle_notif():
            try:
                # Notifications: 0=Disabled (Quiet), 1=Enabled (Loud)
                # If muted (we want Silence/DND), set to 0.
                toast_val = 0 if self.notifications_muted else 1
                
                print(f"Setting Notifications to: {toast_val}")
                
                # Command chain for multiple keys
                cmds = []
                
                # 1. Global Toasts (The big switch) - This is the standard "Notifications" toggle
                cmds.append(f'Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings" -Name "NOC_GLOBAL_SETTING_TOASTS_ENABLED" -Value {toast_val} -Force -ErrorAction SilentlyContinue')
                
                # 2. Try DND key if available
                dnd_val = 1 if self.notifications_muted else 0
                
                full_cmd = "; ".join(cmds)
                os.system(f'powershell -Command "{full_cmd}"')
                
            except Exception as e:
                print(f"Could not toggle notifications: {e}")
        threading.Thread(target=toggle_notif, daemon=True).start()
    
    def _check_focus_lost(self):
        """Check if focus was truly lost to another app and close menu"""
        if not self.settings_menu:
            return
        try:
            # Check if focus is still within our app
            focused = self.root.focus_get()
            if focused is None:
                # Focus went to another app - close menu
                self._close_settings_menu()
        except:
            pass
    
    def _update_bell_label(self):
        """Update bell label based on mute state"""
        if getattr(self, 'notifications_muted', False):
            self.bell_label.config(text="🔕")
        else:
            self.bell_label.config(text="🔔")
    
    def _draw_toggle(self, canvas, is_on):
        """Old toggle - keeping for compatibility"""
        canvas.delete("all")
        if is_on:
            canvas.create_oval(0, 0, 44, 24, fill="#34C759", outline="")
            canvas.create_oval(20, 2, 42, 22, fill="white", outline="")
        else:
            canvas.create_oval(0, 0, 44, 24, fill="#ccc", outline="")
            canvas.create_oval(2, 2, 24, 22, fill="white", outline="")
    
    def _draw_pill_toggle(self, canvas, is_on):
        """Pill-shaped toggle switch - black when on - HIGH RES POLYGON"""
        canvas.delete("all")
        w, h = 40, 22
        
        # Prepare knob image if needed
        if not hasattr(self, 'toggle_knob_img'):
            self.toggle_knob_img = self.create_smooth_circle(h-4, "white", None, 0)
            
        knob_r = (h-4)//2
        center_y = h//2 # Vertical center of canvas
        
        if is_on:
            # Black background pill (on)
            if not hasattr(self, 'pill_on_img'):
                self.pill_on_img = self.create_smooth_rounded_rect(w, h, h//2, "black", None, 0)
            canvas.create_image(w//2, h//2, image=self.pill_on_img)
            
            # White circle on right
            # Left edge: w-h+2. Center X: w-h+2 + r
            center_x = (w-h+2) + knob_r
            canvas.create_image(center_x + 1, center_y, image=self.toggle_knob_img)
        else:
            # Gray background pill (off)
            if not hasattr(self, 'pill_off_img'):
                self.pill_off_img = self.create_smooth_rounded_rect(w, h, h//2, "#ccc", None, 0)
            canvas.create_image(w//2, h//2, image=self.pill_off_img)
            
            # White circle on left
            # Left edge: 2. Center X: 2 + r
            center_x = 2 + knob_r
            canvas.create_image(center_x + 1, center_y, image=self.toggle_knob_img)
    
    def _draw_bell_icon(self, canvas, is_muted):
        """Bell icon - outline with slash when muted, filled when not"""
        canvas.delete("all")
        if is_muted:
            # Outline bell with slash
            canvas.create_text(12, 12, text="🔕", font=("Segoe UI Emoji", 14))
        else:
            # Filled bell
            canvas.create_text(12, 12, text="🔔", font=("Segoe UI Emoji", 14))
    
    def _draw_rounded_popup(self, canvas, w, h, r, border_color):
        """Draw rounded rectangle popup border"""
        # Draw rounded rectangle with thin border
        canvas.create_arc(0, 0, 2*r, 2*r, start=90, extent=90, outline=border_color, style="arc")
        canvas.create_arc(w-2*r, 0, w, 2*r, start=0, extent=90, outline=border_color, style="arc")
        canvas.create_arc(0, h-2*r, 2*r, h, start=180, extent=90, outline=border_color, style="arc")
        canvas.create_arc(w-2*r, h-2*r, w, h, start=270, extent=90, outline=border_color, style="arc")
        canvas.create_line(r, 0, w-r, 0, fill=border_color)
        canvas.create_line(r, h, w-r, h, fill=border_color)
        canvas.create_line(0, r, 0, h-r, fill=border_color)
        canvas.create_line(w, r, w, h-r, fill=border_color)
    
    def _animate_gear(self, degrees):
        """Rotate the gear icon by specified degrees"""
        if not hasattr(self, 'gear_rotation'):
            self.gear_rotation = 0
        
        self.gear_rotation = (self.gear_rotation + degrees) % 360
        
        # Try to rotate the settings icon if using images
        try:
            square = Image.open("settings_square.png").resize((36, 36), Image.Resampling.LANCZOS)
            gear = Image.open("settings_gear.png").resize((24, 24), Image.Resampling.LANCZOS)
            # Rotate gear
            rotated_gear = gear.rotate(self.gear_rotation, resample=Image.Resampling.BICUBIC, expand=False)
            # Paste rotated gear on square
            square.paste(rotated_gear, (6, 6), rotated_gear if rotated_gear.mode == 'RGBA' else None)
            self.settings_icon = ImageTk.PhotoImage(square)
            self.settings_btn.config(image=self.settings_icon)
        except:
            # Fallback - can't animate emoji easily
            pass
    
    def _menu_click(self, cmd):
        self._close_settings_menu()
        cmd()
    
    def _check_menu_click(self, event):
        if not self.settings_menu or not self.settings_menu.winfo_exists():
            return
        
        # Ignore clicks on settings button (it handles its own toggle)
        sx, sy = self.settings_btn.winfo_rootx(), self.settings_btn.winfo_rooty()
        sw, sh = self.settings_btn.winfo_width(), self.settings_btn.winfo_height()
        if sx <= event.x_root <= sx + sw and sy <= event.y_root <= sy + sh:
            return
        
        # Check if click is outside menu
        mx, my = self.settings_menu.winfo_rootx(), self.settings_menu.winfo_rooty()
        mw, mh = self.settings_menu.winfo_width(), self.settings_menu.winfo_height()
        if not (mx <= event.x_root <= mx + mw and my <= event.y_root <= my + mh):
            self._close_settings_menu()
    
    def _close_settings_menu(self):
        # Unbind click handler
        try:
            if hasattr(self, '_menu_click_binding'):
                self.root.unbind("<Button-1>", self._menu_click_binding)
                del self._menu_click_binding
        except:
            pass
        
        # Unbind configure handler
        try:
            if hasattr(self, '_menu_configure_binding'):
                self.root.unbind("<Configure>", self._menu_configure_binding)
                del self._menu_configure_binding
        except:
            pass
        
        # Unbind root focus out
        try:
            if hasattr(self, '_root_focus_out_binding'):
                self.root.unbind("<FocusOut>", self._root_focus_out_binding)
                del self._root_focus_out_binding
        except:
            pass

        if self.settings_menu:
            try:
                if self.settings_menu.winfo_exists():
                    self.settings_menu.destroy()
            except:
                pass
        self.settings_menu = None
    
    def _toggle_notifications_click(self):
        """Handle click on notifications toggle"""
        self.notifications_muted = not getattr(self, 'notifications_muted', False)
        self._draw_pill_toggle(self.toggle_canvas, self.notifications_muted)
        
        # Update bell label
        if hasattr(self, 'bell_label'):
            self._update_bell_label()
        
        # Toggle Windows notifications (run in background to avoid lag)
        import threading
        def toggle_notif():
            try:
                if self.notifications_muted:
                    os.system('powershell -Command "Set-ItemProperty -Path HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings -Name NOC_GLOBAL_SETTING_TOASTS_ENABLED -Value 0"')
                else:
                    os.system('powershell -Command "Set-ItemProperty -Path HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings -Name NOC_GLOBAL_SETTING_TOASTS_ENABLED -Value 1"')
            except Exception as e:
                print(f"Could not toggle notifications: {e}")
        threading.Thread(target=toggle_notif, daemon=True).start()
    
    def toggle_notifications(self, toggle_canvas):
        """Legacy method - kept for compatibility"""
        self._toggle_notifications_click()
    
    def show_founders(self):
        # Placeholder - will implement with popup later
        messagebox.showinfo("Founders", "Founders popup coming soon!")
    
    def show_whats_new(self):
        messagebox.showinfo("What's New", "ZenTap v27.0\n\n• Settings menu\n• Browser tab blocking\n• Notifications silencer")
    
    def unpair_usb(self):
        if messagebox.askyesno("Unpair USB Key", "Are you sure you want to unpair your USB key?"):
            self.paired = False
            self.init_pairing()

    def trigger_pulse(self):
        # Full screen pulse logic (Simplified from V26)
        p = tk.Toplevel(self.root)
        p.attributes("-topmost", True, "-fullscreen", True, "-transparentcolor", "yellow", "-alpha", 0.3)
        p.configure(bg="yellow")
        c = tk.Canvas(p, bg="yellow", highlightthickness=0)
        c.pack(fill="both", expand=True)
        
        w, h = p.winfo_screenwidth(), p.winfo_screenheight()
        cx, cy = w//2, h//2
        r = 0
        def anim():
            nonlocal r
            c.delete("all")
            c.create_oval(cx-r, cy-r, cx+r, cy+r, outline="#FFB7C5", width=20)
            r += 40
            if r < w: p.after(16, anim)
            else: p.destroy()
        anim()

    def loop(self, apps):
        while self.is_active:
            # Block apps
            procs = {p.info['name'].lower() for p in psutil.process_iter(['name'])}
            for app in apps:
                target = APP_MAP.get(app['name'], app['name'].lower().replace(" ","")+".exe").lower()
                if target in procs:
                    for p in psutil.process_iter(['name']):
                        if p.info['name'].lower() == target:
                            try: p.terminate(); self.show_hud(f"Blocked: {app['name']}")
                            except: pass
            
            # Block browser tabs by keyword
            if self.web_keywords:
                try:
                    for item in self.web_keywords:
                        # Handle dict (new) or string (legacy)
                        if isinstance(item, dict):
                            kw = item.get('keyword', '')
                        else:
                            kw = item
                            
                        if not kw or not kw.strip(): continue
                        windows = gw.getWindowsWithTitle(kw)
                        for win in windows:
                            try:
                                win.activate()
                                time.sleep(0.1)
                                pyautogui.hotkey('ctrl', 'w')
                                self.show_hud(f"Blocked Tab: {kw}")
                            except: pass
                except: pass
            
            time.sleep(1)

    def show_hud(self, msg):
        self.root.after(0, lambda: self._hud(msg))

    def _hud(self, msg):
        h = tk.Toplevel(self.root)
        # Use #010101 (nearly black) for transparency key to blend edges with black popup
        trans_col = "#010101"
        h.overrideredirect(True); h.attributes("-topmost", True, "-alpha", 0.90, "-transparentcolor", trans_col)
        h.configure(bg=trans_col)
        w, ht = 400, 60
        x = (h.winfo_screenwidth()-w)//2
        y = (h.winfo_screenheight()-ht)//2
        h.geometry(f"{w}x{ht}+{x}+{y}")
        
        c = tk.Canvas(h, width=w, height=ht, bg=trans_col, highlightthickness=0)
        c.pack()
        
        # Rounded Rect Overlay
        r = ht // 2
        
        # Cache image if needed
        # Use a fresh cache key or just regenerate since it's transient
        bg_img = self.create_smooth_rounded_rect(w, ht, r, "black", None)
        
        # Keep ref on window itself so it persists as long as window matches
        h.bg_img = bg_img 
             
        c.create_image(w//2, ht//2, image=bg_img)
        c.create_text(w//2, ht//2, text=msg, fill="white", font=APP_FONT_BOLD)
        h.after(2000, h.destroy)

    def on_closing(self):
        self.is_active = False
        self.root.destroy()
        sys.exit()



class ManageAppsWindow:
    def __init__(self, parent, apps, web_keywords, on_update, on_warn):
        self.parent = parent
        self.apps = apps
        self.web_keywords = web_keywords  # Reference to the list
        self.on_update = on_update
        self.on_warn = on_warn
        self._load_job = None  # Track pending load jobs
        
        # Pre-load button images for faster rendering
        # ADJUST SIZES HERE: (width, height) for each button
        try:
            # Tab buttons: Apps = 80x36, Websites = 100x36
            apps_size = (80, 36)
            websites_size = (100, 36)
            add_size = (80, 42)
            
            self.apps_selected_img = ImageTk.PhotoImage(
                Image.open("apps_selected.png").resize(apps_size, Image.Resampling.LANCZOS))
            self.apps_unselected_img = ImageTk.PhotoImage(
                Image.open("apps_unselected.png").resize(apps_size, Image.Resampling.LANCZOS))
            self.websites_selected_img = ImageTk.PhotoImage(
                Image.open("websites_selected.png").resize(websites_size, Image.Resampling.LANCZOS))
            self.websites_unselected_img = ImageTk.PhotoImage(
                Image.open("websites_unselected.png").resize(websites_size, Image.Resampling.LANCZOS))
            self.add_button_img = ImageTk.PhotoImage(
                Image.open("add_button.png").resize(add_size, Image.Resampling.LANCZOS))
        except Exception as e:
            print(f"Warning: Could not load button images: {e}")
            self.apps_selected_img = None
            self.apps_unselected_img = None
            self.websites_selected_img = None
            self.websites_unselected_img = None
            self.add_button_img = None
        
        self.win = tk.Toplevel(parent)
        self.win.geometry("450x650")
        self.win.configure(bg="white")
        self.win.resizable(True, True)  # Enable resizing
        self.win.minsize(350, 400)  # Minimum size
        self.win.transient(parent) # keep on top
        
        # Center
        x = parent.winfo_x() + (parent.winfo_width()//2) - 225
        y = parent.winfo_y() + (parent.winfo_height()//2) - 325
        self.win.geometry(f"+{int(x)}+{int(y)}")
        
        self.show_summary()

    def show_summary(self):
        # Cancel any pending load jobs to prevent TclError
        if self._load_job:
            self.win.after_cancel(self._load_job)
            self._load_job = None
        
        for w in self.win.winfo_children(): w.destroy()
        self.win.update_idletasks()  # Force immediate refresh
        
        selected_apps = [a for a in self.apps if a['checked']]
        
        # Prepare websites list
        selected_websites = []
        for item in self.web_keywords:
            if isinstance(item, dict):
                selected_websites.append({'name': item.get('keyword', '?'), 'icon': item.get('icon'), 'type': 'web'})
            else:
                selected_websites.append({'name': item, 'icon': None, 'type': 'web'})
        
        total_items = len(selected_apps) + len(selected_websites)
        
        # Header - reduced bottom padding
        h = tk.Frame(self.win, bg="white")
        h.pack(fill="x", padx=20, pady=(20, 5))
        
        tk.Label(h, text="Ready to Block", font=("Roboto Medium", 18), bg="white").pack(side="left")
        
        # Edit Button - using image file
        try:
            edit_img = Image.open("appSelect_edit.png").resize((32, 32), Image.Resampling.LANCZOS)
            self.edit_icon = ImageTk.PhotoImage(edit_img)
            edit_btn = tk.Label(h, image=self.edit_icon, bg="white", cursor="hand2")
            edit_btn.pack(side="right")
            edit_btn.bind("<Button-1>", lambda e: self.show_selector())
        except:
            # Fallback to text if image not found
            edit_btn = tk.Label(h, text="Edit", font=("Roboto", 10), fg="#666", bg="white", cursor="hand2")
            edit_btn.pack(side="right")
            edit_btn.bind("<Button-1>", lambda e: self.show_selector())
        
        # Subtitle - close to header
        subtitle_text = f"{total_items} items blocked"
        if len(selected_apps) > 0 and len(selected_websites) > 0:
            subtitle_text = f"{len(selected_apps)} apps, {len(selected_websites)} sites blocked"
        
        tk.Label(self.win, text=subtitle_text, font=("Roboto", 10), fg="gray", bg="white").pack(anchor="w", padx=20, pady=0)
        
        # List
        sf = tk.Frame(self.win, bg="white")
        sf.pack(fill="both", expand=True, padx=20)
        
        if total_items == 0:
             tk.Label(sf, text="No apps or websites selected.", font=("Roboto", 12), fg="gray", bg="white").pack(pady=20)
        
        # Combine lists for display
        combined_list = []
        for a in selected_apps:
            combined_list.append({'name': a['name'], 'icon': a['icon'], 'type': 'app'})
        for w in selected_websites:
            combined_list.append(w)
            
        for item in combined_list:
            row = tk.Frame(sf, bg="white", pady=8)
            row.pack(fill="x")
            
            # Icon
            if item['icon']:
                tk.Label(row, image=item['icon'], bg="white").pack(side="left", padx=(0, 15))
            elif item['type'] == 'web':
                 # Fallback for website - gray circle with letter
                 # Create a simple fallback image on the fly
                 try:
                     f_img = Image.new('RGBA', (32, 32), (0,0,0,0))
                     d = ImageDraw.Draw(f_img)
                     d.ellipse((0,0,32,32), fill="#eee")
                     # Draw letter
                     letter = item['name'][0].upper()
                     # diverse centering hack
                     d.text((10, 8), letter, fill="#666", font=ImageFont.truetype("arial.ttf", 16) if os.name=='nt' else None)
                     
                     photo = ImageTk.PhotoImage(f_img)
                     item['icon_fallback'] = photo # Keep ref
                     tk.Label(row, image=photo, bg="white").pack(side="left", padx=(0, 15))
                 except:
                     # Absolute fallback
                     tk.Label(row, text="🌐", font=("Segoe UI Emoji", 16), bg="white").pack(side="left", padx=(0, 10))
            
            # Name - Bold/Medium font
            tk.Label(row, text=item['name'], font=("Roboto Medium", 12), bg="white").pack(side="left")
            
            # Divider
            tk.Frame(sf, height=1, bg="#eee").pack(fill="x", pady=2)

        # Close Button
        b_frame = tk.Frame(self.win, bg="white", pady=20)
        b_frame.pack(side="bottom", fill="x")
        
        btn = tk.Canvas(b_frame, width=350, height=50, bg="white", highlightthickness=0)
        btn.pack()
        self.draw_pill_btn(btn, 350, 50, "#f2f2f2", "Close", "black")
        btn.bind("<Button-1>", lambda e: self.win.destroy())

    def show_selector(self):
        for w in self.win.winfo_children(): w.destroy()
        self.current_tab = "apps"  # Track active tab
        
        # Header
        h = tk.Frame(self.win, bg="white")
        h.pack(fill="x", padx=20, pady=(20, 10))
        tk.Label(h, text="Select Apps", font=("Roboto Medium", 18), bg="white").pack(side="left")
        
        # Tab Buttons Frame
        tab_frame = tk.Frame(self.win, bg="white")
        tab_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        # Apps Tab - Canvas for pill shape
        self.apps_tab_canvas = tk.Canvas(tab_frame, width=80, height=36, bg="white", highlightthickness=0)
        self.apps_tab_canvas.pack(side="left", padx=(0, 8))
        self.apps_tab_canvas.bind("<Button-1>", lambda e: self.switch_tab("apps"))
        
        # Websites Tab - Canvas for pill shape
        self.web_tab_canvas = tk.Canvas(tab_frame, width=100, height=36, bg="white", highlightthickness=0)
        self.web_tab_canvas.pack(side="left")
        self.web_tab_canvas.bind("<Button-1>", lambda e: self.switch_tab("websites"))
        
        # Draw initial tab states
        self._draw_tab_buttons()
        
        # Content container
        self.tab_content = tk.Frame(self.win, bg="white")
        self.tab_content.pack(fill="both", expand=True)
        
        # Done Button (Centered) - store reference for tab switching
        self.done_btn = tk.Canvas(self.win, width=250, height=50, bg="white", highlightthickness=0)
        self.done_btn.pack(side="bottom", pady=20)
        self.draw_pill_btn(self.done_btn, 250, 50, "#f2f2f2", "Done", "black")
        self.done_btn.bind("<Button-1>", lambda e: self.show_summary())
        
        # Show apps tab by default
        self.show_apps_tab()
    
    def _draw_tab_buttons(self):
        # Apps tab
        self.apps_tab_canvas.delete("all")
        if self.current_tab == "apps":
            # Selected - use image
            if self.apps_selected_img:
                self.apps_tab_canvas.create_image(40, 18, image=self.apps_selected_img)
            else:
                self.draw_rounded_rect(self.apps_tab_canvas, 0, 0, 80, 36, 18, "#444")
                self.apps_tab_canvas.create_text(40, 18, text="Apps", font=("Roboto Medium", 11), fill="white")
        else:
            # Unselected - use image
            if self.apps_unselected_img:
                self.apps_tab_canvas.create_image(40, 18, image=self.apps_unselected_img)
            else:
                self.draw_rounded_rect(self.apps_tab_canvas, 0, 0, 80, 36, 18, "white")
                self.apps_tab_canvas.create_oval(0, 0, 36, 36, outline="black", width=2)
                self.apps_tab_canvas.create_oval(44, 0, 80, 36, outline="black", width=2)
                self.apps_tab_canvas.create_line(18, 1, 62, 1, fill="black", width=2)
                self.apps_tab_canvas.create_line(18, 35, 62, 35, fill="black", width=2)
                self.apps_tab_canvas.create_rectangle(18, 2, 62, 34, fill="white", outline="")
                self.apps_tab_canvas.create_text(40, 18, text="Apps", font=("Roboto", 11), fill="black")
        
        # Websites tab
        self.web_tab_canvas.delete("all")
        if self.current_tab == "websites":
            # Selected - use image
            if self.websites_selected_img:
                self.web_tab_canvas.create_image(50, 18, image=self.websites_selected_img)
            else:
                self.draw_rounded_rect(self.web_tab_canvas, 0, 0, 100, 36, 18, "#444")
                self.web_tab_canvas.create_text(50, 18, text="Websites", font=("Roboto Medium", 11), fill="white")
        else:
            # Unselected - use image
            if self.websites_unselected_img:
                self.web_tab_canvas.create_image(50, 18, image=self.websites_unselected_img)
            else:
                self.draw_rounded_rect(self.web_tab_canvas, 0, 0, 100, 36, 18, "white")
                self.web_tab_canvas.create_oval(0, 0, 36, 36, outline="black", width=2)
                self.web_tab_canvas.create_oval(64, 0, 100, 36, outline="black", width=2)
                self.web_tab_canvas.create_line(18, 1, 82, 1, fill="black", width=2)
                self.web_tab_canvas.create_line(18, 35, 82, 35, fill="black", width=2)
                self.web_tab_canvas.create_rectangle(18, 2, 82, 34, fill="white", outline="")
                self.web_tab_canvas.create_text(50, 18, text="Websites", font=("Roboto", 11), fill="black")
    
    def switch_tab(self, tab):
        if tab == self.current_tab:
            return
        self.current_tab = tab
        
        # Cancel any pending load jobs to prevent TclError
        if hasattr(self, '_load_job') and self._load_job:
            self.win.after_cancel(self._load_job)
            self._load_job = None
        
        # Redraw tab buttons
        self._draw_tab_buttons()
        
        # Completely destroy and recreate tab_content frame for clean switch
        self.tab_content.destroy()
        self.tab_content = tk.Frame(self.win, bg="white")
        self.tab_content.pack(fill="both", expand=True, before=self.done_btn)
        self.win.update_idletasks()
        
        # Show appropriate content
        if tab == "apps":
            self.show_apps_tab()
        else:
            self.show_websites_tab()
    
    def show_apps_tab(self):
        # Note: tab_content is recreated in switch_tab, so no need to destroy children here
        
        # Search Bar - responsive pill
        s_frame = tk.Frame(self.tab_content, bg="white")
        s_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        self.search_canvas = tk.Canvas(s_frame, height=40, bg="white", highlightthickness=0)
        self.search_canvas.pack(fill="x")
        
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(self.search_canvas, bg="#f2f2f2", bd=0, font=("Roboto", 11), textvariable=self.search_var)
        
        def redraw_pill(e):
            self.search_canvas.delete("all")
            h = e.height
            w = e.width
            if h > 0 and w > 0:
                self.draw_rounded_rect(self.search_canvas, 1, 1, w-2, h-2, h//2 - 1, "#f2f2f2")
                self.search_entry.place(x=h//2, y=h//2, anchor="w", width=w-h)

        self.search_canvas.bind("<Configure>", redraw_pill)
        self.search_entry.bind("<KeyRelease>", self.perform_search)
        
        # Info
        self.info_lbl = tk.Label(self.tab_content, text="", font=("Roboto Medium", 10), fg="#444", bg="white")
        self.info_lbl.pack(pady=5)
        self.update_info_label()

        # Scrollable Content - responsive width
        self.list_canvas = tk.Canvas(self.tab_content, bg="white", highlightthickness=0)
        self.list_frame = tk.Frame(self.list_canvas, bg="white")
        
        self.list_canvas.pack(fill="both", expand=True, padx=10)
        self.list_window = self.list_canvas.create_window((0,0), window=self.list_frame, anchor="nw")
        
        self._resize_job = None
        def on_canvas_configure(e):
            if self._resize_job:
                self.win.after_cancel(self._resize_job)
            self._resize_job = self.win.after(50, lambda: self.list_canvas.itemconfig(self.list_window, width=e.width))
        self.list_canvas.bind("<Configure>", on_canvas_configure)
        
        def on_frame_conf(e): 
            self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all"))
        self.list_frame.bind("<Configure>", on_frame_conf)
        
        def _on_mousewheel(event):
            self.list_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.list_canvas.bind("<MouseWheel>", _on_mousewheel)
        self.list_frame.bind("<MouseWheel>", _on_mousewheel)
        self.win.bind("<MouseWheel>", _on_mousewheel)
        
        self.populate_list(self.apps)
    
    def show_websites_tab(self):
        # Note: tab_content is recreated in switch_tab, so no need to destroy children here
        
        # Instructions
        tk.Label(self.tab_content, text="Block browser tabs containing these keywords:", 
                 font=("Roboto", 11), bg="white", fg="#999").pack(anchor="w", padx=20, pady=(10, 15))
        
        # Add keyword input row
        add_frame = tk.Frame(self.tab_content, bg="white")
        add_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # Add button - pack FIRST (side=right) to ensure it gets space
        if self.add_button_img:
            add_btn = tk.Label(add_frame, image=self.add_button_img, bg="white", cursor="hand2")
            add_btn.pack(side="right", padx=(10, 0))
            add_btn.bind("<Button-1>", lambda e: self.add_keyword())
        else:
            add_btn_canvas = tk.Canvas(add_frame, width=80, height=42, bg="white", highlightthickness=0)
            add_btn_canvas.pack(side="right", padx=(10, 0))
            self.draw_rounded_rect(add_btn_canvas, 0, 0, 80, 42, 8, "black")
            add_btn_canvas.create_text(40, 21, text="+ Add", font=("Roboto Medium", 11), fill="white")
            add_btn_canvas.bind("<Button-1>", lambda e: self.add_keyword())
        
        # Input field with rounded background - pack AFTER button
        input_container = tk.Frame(add_frame, bg="white")
        input_container.pack(side="left", fill="x", expand=True)
        
        self.keyword_canvas = tk.Canvas(input_container, height=42, bg="white", highlightthickness=0)
        self.keyword_canvas.pack(fill="x")
        
        self.keyword_var = tk.StringVar()
        self.keyword_entry = tk.Entry(self.keyword_canvas, textvariable=self.keyword_var, 
                                       font=("Roboto", 11), bg="#f2f2f2", bd=0, relief="flat")
        self.keyword_entry.bind("<Return>", lambda e: self.add_keyword())
        
        def redraw_input(e):
            self.keyword_canvas.delete("all")
            w, h = e.width, e.height
            if w > 0 and h > 0:
                # Draw rounded rectangle background
                r = 8
                self.draw_rounded_rect(self.keyword_canvas, 0, 0, w, h, r, "#f2f2f2")
                # Place entry inside
                self.keyword_entry.place(x=12, y=h//2, anchor="w", width=w-24, height=h-12)
        
        self.keyword_canvas.bind("<Configure>", redraw_input)
        
        # List of keywords
        self.keywords_frame = tk.Frame(self.tab_content, bg="white")
        self.keywords_frame.pack(fill="both", expand=True, padx=20)
        
        self.refresh_keywords_list()
    
    def add_keyword(self):
        kw = self.keyword_var.get().strip()
        if not kw:
            return
        
        # Check if keyword already exists
        for item in self.web_keywords:
            existing_kw = item.get('keyword') if isinstance(item, dict) else item
            if existing_kw.lower() == kw.lower():
                return  # Already exists
        
        # Create entry with placeholder (no icon yet)
        entry = {'keyword': kw, 'icon': None, 'icon_pil': None}
        self.web_keywords.append(entry)
        self.keyword_var.set("")
        self.refresh_keywords_list()
        self.on_update()  # Update the main dock
        
        # Fetch favicon in background
        def fetch_icon():
            icon_pil = get_website_favicon(kw)
            if icon_pil:
                entry['icon_pil'] = icon_pil
                entry['icon'] = ImageTk.PhotoImage(icon_pil)
                # Refresh UI on main thread
                if self.win.winfo_exists():
                    self.win.after(0, self.refresh_keywords_list)
                    self.win.after(0, self.on_update)
        
        threading.Thread(target=fetch_icon, daemon=True).start()
    
    def remove_keyword(self, kw):
        # Find and remove the entry with matching keyword
        for item in self.web_keywords[:]:
            item_kw = item.get('keyword') if isinstance(item, dict) else item
            if item_kw == kw:
                self.web_keywords.remove(item)
                break
        self.refresh_keywords_list()
        self.on_update()  # Update the main dock
    
    def refresh_keywords_list(self):
        for w in self.keywords_frame.winfo_children(): w.destroy()
        
        if not self.web_keywords:
            tk.Label(self.keywords_frame, text="No keywords added yet.", 
                     font=("Roboto", 11), fg="#999", bg="white").pack(pady=20)
            return
        
        # Keep icon refs to prevent GC
        if not hasattr(self, '_kw_icons'): self._kw_icons = []
        self._kw_icons.clear()
        
        for item in self.web_keywords:
            # Handle both dict and legacy string format
            if isinstance(item, dict):
                kw = item.get('keyword', '?')
                icon_pil = item.get('icon_pil')
            else:
                kw = item
                icon_pil = None
            
            row = tk.Frame(self.keywords_frame, bg="white")
            row.pack(fill="x", pady=5)
            
            # Icon (if available)
            if icon_pil:
                try:
                    small_icon = icon_pil.resize((24, 24), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(small_icon)
                    self._kw_icons.append(photo)  # Keep ref
                    icon_label = tk.Label(row, image=photo, bg="white")
                    icon_label.pack(side="left", padx=(0, 8))
                except:
                    pass
            
            tk.Label(row, text=kw, font=("Roboto", 11), bg="white").pack(side="left")
            
            remove_btn = tk.Label(row, text="✕", font=("Roboto", 10), 
                                   fg="#999", bg="white", cursor="hand2")
            remove_btn.pack(side="right")
            remove_btn.bind("<Button-1>", lambda e, k=kw: self.remove_keyword(k))

    def perform_search(self, event=None):
        if hasattr(self, '_search_job') and self._search_job:
            self.win.after_cancel(self._search_job)
            
        self._search_job = self.win.after(300, self._do_search)

    def _do_search(self):
        query = self.search_var.get().lower().strip()
        if not query:
            self.populate_list(self.apps)
            return
        
        filtered = [a for a in self.apps if query in a['name'].lower()]
        self.populate_list(filtered)

    def populate_list(self, app_list):
        # Cancel any pending load
        if hasattr(self, '_load_job') and self._load_job:
             self.win.after_cancel(self._load_job)
             
        for w in self.list_frame.winfo_children(): w.destroy()
        
        # Reset scroll - Important: Reset canvas view AND region
        self.list_canvas.yview_moveto(0)
        self.list_canvas.configure(scrollregion=(0,0,1,1)) # Reset to minimal
        
        # Initial chunk
        self._load_queue = app_list[:]
        self._load_chunk()
        
    def _load_chunk(self):
        # Guard: Check if window still exists
        if not self.win.winfo_exists():
            return
        if not self._load_queue: return
        
        chunk = self._load_queue[:15] # Load 15 at a time
        self._load_queue = self._load_queue[15:]
        
        for app in chunk:
            row = tk.Frame(self.list_frame, bg="white") 
            row.pack(fill="x", padx=20, pady=2)
            
            # Hitbox frame
            hitbox = tk.Frame(row, bg="white")
            hitbox.pack(fill="x")
            
            # Checkbox RIGHT
            chk = tk.Canvas(hitbox, width=28, height=28, bg="white", highlightthickness=0)
            chk.pack(side="right", padx=(5, 0))
            self.draw_checkbox(chk, app['checked'])
            
            # Icon LEFT
            if app['icon']:
                tk.Label(hitbox, image=app['icon'], bg="white").pack(side="left", padx=(0, 15))
            
            # Name LEFT - no bold
            name_font = ("Roboto", 11)
            name_lbl = tk.Label(hitbox, text=app['name'], font=name_font, bg="white", anchor="w")
            name_lbl.pack(side="left", fill="x", expand=True)
            
            # Bindings
            action = lambda e, a=app, cv=chk, nl=name_lbl: self.toggle(a, cv, nl)
            hitbox.bind("<Button-1>", action)
            name_lbl.bind("<Button-1>", action)
            chk.bind("<Button-1>", action)
            for child in hitbox.winfo_children():
                try: child.bind("<Button-1>", action)
                except: pass
            
            # Divider
            tk.Frame(row, height=1, bg="#f5f5f5").pack(fill="x", pady=(2,0))

        # Update scrollregion AFTER adding widgets
        self.list_frame.update_idletasks() # Force geometry update
        self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all"))

        if self._load_queue:
            self._load_job = self.win.after(10, self._load_chunk)
        else:
            # Final check just in case
            self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all"))


    def toggle(self, app, cvs, name_lbl):
        count = len([a for a in self.apps if a['checked']])
        if not app['checked'] and count >= 15:
            if self.on_warn: self.on_warn("Max 15 apps allowed.")
            return

        app['checked'] = not app['checked']
        
        if app['checked']:
            app['selection_ts'] = time.time()
        else:
            app['selection_ts'] = 0
            
        self.draw_checkbox(cvs, app['checked'])
        
        font_style = ("Roboto Medium", 11) if app['checked'] else ("Roboto", 11)
        name_lbl.configure(font=font_style)
        
        self.on_update() # Trigger slot update in main window
        self.update_info_label()

    def update_info_label(self):
        c = len([a for a in self.apps if a['checked']])
        self.info_lbl.config(text=f"{c}/15 Apps Blocked")

    def draw_checkbox(self, c, checked):
        c.delete("all")
        if checked:
            c.create_oval(2,2, 26,26, fill="black", outline="black")
            c.create_line(8,14, 12,18, 19,8, fill="white", width=2)
        else:
            c.create_oval(2,2, 26,26, fill="white", outline="#ddd", width=2)
    
    def draw_rounded_rect(self, c, x, y, w, h, r, fill):
        # Helper for rounded rect, assuming path support or multiple ovals
        c.create_oval(x, y, x+r*2, y+r*2, fill=fill, outline=fill)
        c.create_oval(x+w-r*2, y, x+w, y+r*2, fill=fill, outline=fill)
        c.create_oval(x, y+h-r*2, x+r*2, y+h, fill=fill, outline=fill)
        c.create_oval(x+w-r*2, y+h-r*2, x+w, y+h, fill=fill, outline=fill)
        c.create_rectangle(x+r, y, x+w-r, y+h, fill=fill, outline=fill)
        c.create_rectangle(x, y+r, x+w, y+h-r, fill=fill, outline=fill)

    def draw_pill_btn(self, c, w, h, bg, text, fg):
        self.draw_rounded_rect(c, 0, 0, w, h, h//2, bg)
        c.create_text(w//2, h//2, text=text, font=("Roboto Medium", 12), fill=fg)

if __name__ == "__main__":
    root = tk.Tk()
    app = ZenTapApp(root)
    root.mainloop()