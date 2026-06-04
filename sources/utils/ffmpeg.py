import os
import sys
import platform
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SOURCES_DIR = BASE_DIR / "sources"
FFMPEG_BASE = SOURCES_DIR / "FFmpeg"

def get_ffmpeg_path():
    """Return absolute path to FFmpeg executable (project-bundled or system)."""
    system = platform.system().lower()
    
    if system == "windows":
        ffmpeg_exe = FFMPEG_BASE / "windows" / "ffmpeg" / "bin" / "ffmpeg.exe"
    elif system == "darwin":
        ffmpeg_exe = FFMPEG_BASE / "macos" / "ffmpeg"
    elif system == "linux":
        ffmpeg_exe = FFMPEG_BASE / "linux" / "ffmpeg"
    else:
        ffmpeg_exe = None

    if ffmpeg_exe and ffmpeg_exe.exists():
        return str(ffmpeg_exe)

    # Fallback to system FFmpeg
    import shutil
    system_ffmpeg = shutil.which('ffmpeg')
    return system_ffmpeg