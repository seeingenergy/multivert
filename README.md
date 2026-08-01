# multivert

variable pass audio conversion 

Audio conversion in as few clicks as possible. There is a multi-pass option available for emulating the sound of a file that's been passed around on the internet for years, or just to ruin the quality for funsies.

## Requirements
 
ffmpeg
tkinter
tkinterdnd2 (optional)
 
## Setup (Fedora)
 
```bash
# tkinter
sudo dnf install python3-tkinter
 
# ffmpeg
sudo dnf install https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
sudo dnf install ffmpeg
 
# Optional: drag-and-drop support for the file field
pip install --user tkinterdnd2
```
 
## Setup (Windows)
 
- Install Python 3 
- Install ffmpeg on your PATH (e.g. via
 [gyan.dev builds](https://www.gyan.dev/ffmpeg/builds/) or
 `winget install ffmpeg`).
- `pip install tkinterdnd2` for drag-and-drop.
 
## Running
 
```bash
cd /wherever/you/put/multivert
python3 multivert.py
```

