"""Workaround: create directories with trailing spaces in names on Windows."""
import os
import sys

target_dir = r"F:\work_healthy\obsidian_health\.derived\pdf_extract\raw\私域运营课\肖厂长3天笔记\肖厂长深圳线下课PPT -第三天 "

# Use \\?\ prefix for extended-length path support (handles trailing spaces)
unc_path = "\\\\?\\" + os.path.normpath(target_dir)
print(f"Creating directory with UNC path: {unc_path}")
os.makedirs(unc_path, exist_ok=True)
print("Directory created successfully!")

# Verify it exists
if os.path.exists(unc_path):
    print("Verified: directory exists")
else:
    print("ERROR: directory does not exist after creation")
    sys.exit(1)

# Also list contents
entries = os.listdir(unc_path)
print(f"Contents: {entries}")
