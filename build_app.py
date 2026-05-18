import os
import shutil
import subprocess

def main():
    root = os.path.dirname(os.path.abspath(__file__))
    resources_dir = os.path.join(root, "resources")
    build_output_dir = os.path.join(root, "Build")
    
    os.makedirs(resources_dir, exist_ok=True)
    os.makedirs(build_output_dir, exist_ok=True)

    # 1. Copy the generated premium PNG icon
    src_icon = "/Users/serafim/.gemini/antigravity/brain/b619a47e-cd08-423b-93c4-c13d0c9efb1d/app_icon_1779136952110.png"
    dest_png = os.path.join(resources_dir, "icon.png")
    
    if os.path.exists(src_icon):
        shutil.copy(src_icon, dest_png)
        print("✓ Copied source PNG to resources/icon.png")
    else:
        print("⚠️ Source PNG icon not found. Make sure the path is correct.")
        return

    # Force format conversion to true PNG using sips
    print("Converting source icon to native PNG format...")
    subprocess.run([
        "sips", "-s", "format", "png", dest_png, "--out", dest_png
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. Create standard macOS .icns file using sips and iconutil
    iconset_dir = os.path.join(resources_dir, "icon.iconset")
    os.makedirs(iconset_dir, exist_ok=True)

    sizes = [
        ("16x16", 16),
        ("16x16@2x", 32),
        ("32x32", 32),
        ("32x32@2x", 64),
        ("128x128", 128),
        ("128x128@2x", 256),
        ("256x256", 256),
        ("256x256@2x", 512),
        ("512x512", 512),
        ("512x512@2x", 1024)
    ]

    print("Generating macOS iconset sizes...")
    for name, size in sizes:
        out_png = os.path.join(iconset_dir, f"icon_{name}.png")
        subprocess.run([
            "sips", "-s", "format", "png", "-z", str(size), str(size), dest_png, "--out", out_png
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Compile the iconset into an .icns file
    dest_icns = os.path.join(resources_dir, "icon.icns")
    result = subprocess.run(["iconutil", "-c", "icns", iconset_dir, "-o", dest_icns])
    
    # Cleanup iconset folder
    shutil.rmtree(iconset_dir)
    
    if result.returncode != 0 or not os.path.exists(dest_icns):
        print("❌ Failed to compile icon.icns using iconutil.")
        return
        
    print("✓ Successfully generated resources/icon.icns")

    # 3. Run PyInstaller
    spec_path = os.path.join(root, "build.spec")
    print("Running PyInstaller build...")
    
    # Run PyInstaller as a subprocess
    result = subprocess.run([
        ".venv/bin/pyinstaller", spec_path, "--noconfirm"
    ])
    
    if result.returncode == 0:
        print("✓ PyInstaller build completed successfully!")
        
        # Move the compiled .app into the Build directory
        src_app = os.path.join(root, "dist", "Liquid Glass Clipboard.app")
        dest_app = os.path.join(build_output_dir, "Liquid Glass Clipboard.app")
        
        if os.path.exists(dest_app):
            shutil.rmtree(dest_app)
            
        if os.path.exists(src_app):
            shutil.move(src_app, dest_app)
            print(f"✓ Moved 'Liquid Glass Clipboard.app' to workspace Build/ directory!")
        else:
            print("⚠️ Built .app bundle not found in dist/ directory.")
    else:
        print("❌ PyInstaller build failed.")

if __name__ == "__main__":
    main()
