"""
Ping Gu - Standalone Windows Executable Build Script (build_exe.py)
Automates PyInstaller packaging for PingGu.exe:
- Generates/verifies pingu.ico from pingu.jpg
- Bundles application assets (pingu.jpg, pingu.ico, CustomTkinter assets)
- Compiles a single-file, windowed (no-console) Windows binary into dist/PingGu.exe
"""

import os
import shutil
import subprocess
import sys
import time

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from presets import ensure_app_icon, resource_path


def print_banner(text: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def build_executable() -> bool:
    print_banner("PING GU - STANDALONE WINDOWS EXECUTABLE BUILDER")
    start_time = time.time()

    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    # 1. Verify / Generate Application Icon
    print("\n[1/4] Checking Application Icon (pingu.ico)...")
    ico_path = ensure_app_icon()
    if not ico_path or not os.path.exists(ico_path):
        print("[ERROR] Failed to find or generate pingu.ico from pingu.jpg!")
        return False
    print(f"      OK: Application icon verified at: {ico_path} ({os.path.getsize(ico_path)} bytes)")

    jpg_path = os.path.join(project_dir, "pingu.jpg")
    if not os.path.exists(jpg_path):
        print("[ERROR] Missing pingu.jpg in project directory!")
        return False
    print(f"      OK: Application logo verified at: {jpg_path} ({os.path.getsize(jpg_path)} bytes)")

    # 2. Clean previous build artifacts
    print("\n[2/4] Cleaning previous build artifacts...")
    for folder in ["build", "dist"]:
        folder_path = os.path.join(project_dir, folder)
        if os.path.exists(folder_path):
            try:
                shutil.rmtree(folder_path)
                print(f"      OK: Removed stale '{folder}/' directory")
            except Exception as e:
                print(f"      Warning: Could not remove '{folder}/': {e}")

    spec_file = os.path.join(project_dir, "PingGu.spec")
    if os.path.exists(spec_file):
        try:
            os.remove(spec_file)
            print("      OK: Removed stale 'PingGu.spec'")
        except Exception as e:
            print(f"      Warning: Could not remove '{spec_file}': {e}")

    # 3. Construct PyInstaller Arguments
    print("\n[3/4] Invoking PyInstaller Compilation Pipeline...")
    # On Windows, add-data format is "source;destination"
    add_data_jpg = f"pingu.jpg;."
    add_data_ico = f"pingu.ico;."

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", "PingGu",
        "--icon", "pingu.ico",
        "--add-data", add_data_jpg,
        "--add-data", add_data_ico,
        "--collect-all", "customtkinter",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.ImageTk",
        "--hidden-import", "icmplib",
        "--hidden-import", "requests",
        "--hidden-import", "psutil",
        "main.py"
    ]

    print(f"      Command: {' '.join(cmd)}\n")
    proc = subprocess.run(cmd, cwd=project_dir)
    if proc.returncode != 0:
        print(f"\n[ERROR] PyInstaller compilation failed with exit code {proc.returncode}!")
        return False

    # 4. Verify Built Executable
    print("\n[4/4] Verifying Final Standalone Executable...")
    exe_path = os.path.join(project_dir, "dist", "PingGu.exe")
    if not os.path.exists(exe_path):
        print(f"[ERROR] Expected output binary not found at '{exe_path}'!")
        return False

    exe_size_bytes = os.path.getsize(exe_path)
    exe_size_mb = exe_size_bytes / (1024 * 1024)
    elapsed = time.time() - start_time

    print_banner("STANDALONE EXECUTABLE BUILT SUCCESSFULLY!")
    print(f"  Target Binary : {exe_path}")
    print(f"  File Size     : {exe_size_mb:.2f} MB ({exe_size_bytes:,} bytes)")
    print(f"  Build Time    : {elapsed:.1f} seconds")
    print(f"  Packaging     : Single-file portable executable (Zero installation required)")
    print("=" * 70)
    print("NOOT NOOT! 🐧\n")
    return True


if __name__ == "__main__":
    success = build_executable()
    sys.exit(0 if success else 1)
