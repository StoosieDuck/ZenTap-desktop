try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageFilter
    print("PIL: OK")
    import pygetwindow as gw
    print("pygetwindow: OK")
    import pyautogui
    print("pyautogui: OK")
    import trimesh
    print("trimesh: OK")
    import pyrender
    print("pyrender: OK")
    import numpy as np
    print("numpy: OK")
except Exception as e:
    print(f"FAILED: {e}")
