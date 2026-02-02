import subprocess
try:
    output = subprocess.check_output(["python", "test_pyrender_crash.py"], stderr=subprocess.STDOUT)
    print(output.decode())
except subprocess.CalledProcessError as e:
    print(e.output.decode())
except Exception as e:
    print(f"Runner error: {e}")
