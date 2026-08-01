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

## The long-enough story of why this exists.
 In early 2022, I noticed a trend that would later evolve in tandem with the nostalgia-soaked Frutiger aero design craze. I noticed that trend pop up in several places, from the surreal world of Yabujin to a bespoke track from MIKE's 'Weight of the World' tape called allstar. That trend is a kind of audio degradation that aims to emulate audio codec artifacting. This trend can honestly be traced back to the mid 2010s 'deep fried' meme trend, although doesn't directly influence this trend in music per-se. I can, however, remember a video of a Mario dance animation set to 'American Girl' by Estelle that was so compressed it was barely identifiable. It wouldn't leave my head, *because I unironically kind of liked it*.
 
 Fast forward to 2024, and I'm messing around on my phone with this notably robust free audio converter app, and I discover that you can convert WAV files all the way from their usual sample rate of 41000 Hz all the way down to 1000 Hz. This blew my mind when I heard it, especially with the piece that I used, because it basically deep fried the audio so much to the point where it completely transformed the sound to what was essentially a few sine waves playing with this beautiful resonance that became the primary impetus of my project 'open-world', released under the alias 'seeing energy'. I became fascinated with audio conversion, and particularly the 'sound' each codec would make at various qualities from an aesthetic perspective. Thusly, this stylistic element re-appeared through my discography, influenced by early-internet nostalgia, transformed by the seeing energy project, all the way through to the present day, 2026.
 
 As a musician, it became that I encountered audio conversion at basically every corner. However, as an audio conversion purist of sorts, I was never satisfied with plugins that merely *emulated* what audio conversion sounds like, and besides, it's so easy to do. Obviously, on a practical basis, converting audio files multiple times over is very clunky, further complicated by over-ambitious devs that jam their programs full of hidden menus, esoteric ffmpeg features that nobody actually uses, and worst of all, paid subscriptions! I had to reconcile dealing with this part of my musical process along with the absolute necessity of storing a music collection on a phone with only 64 GB of storage.
 
 The original intention was to vibe code a clutter-free audio converter with the immediacy of a musical instrument. Basically an ffmpeg command with buttons. However, when I took into account how many times I would perform multiple passes to convert the audio in a musical use-case, I had the idea to create a program that would allow me to apply multiple conversion steps simultaneously. These two tensions in my life resulted in Multivert. A simple program for a simple function.
 
Version 1.0 ideally will include:
- Preview
- Export file at select steps for practical purposes
- A/B different chains
- Obscure/obsolete codecs outside of ffmpeg's scope
 
I may also post this program without the chain feature for posterity. This program contains the full scope of the ethos I want for an audio converter. My true vision is a more bespoke program for this particular, more musical function.

`VIBE CODED` if you dig through the code, you'll find all the extra stuff ai leaves in there. I'll remove it in future versions.
