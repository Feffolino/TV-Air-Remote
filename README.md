# TV Air Remote

Control a Samsung Smart TV (Tizen) with your hands. A webcam connected to your
computer watches your hands, [MediaPipe](https://ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer)
tracks them in real time, and the program sends the matching remote-control key
to the TV over your local network.

It is built for everyday TV watching: volume and channels need a single open
hand, while menu navigation uses both hands.

- **Open palm as a joystick**: move it a little to change volume or channel,
  hold it to keep going, move it further to go faster.
- **Two hands = navigation**: the left hand moves left, the right hand moves
  right, either one moves up and down.
- **Click** (close and reopen your hand) = OK, which also pauses and resumes
  videos. **Thumb pointing left** = back. **Fist** held for 1 s = Home.
- On-screen legend of the available commands, in English or Italian.
- Automatic reconnection to the TV, Wake-on-LAN power on, dry-run mode for
  testing without a TV.

## Requirements

- Python 3.11 or 3.12
- A webcam (a laptop's built-in one is fine)
- A Samsung Tizen TV (2016 models onwards) on the same network as the computer
- On Linux: the `libegl1` and `libgles2` libraries (needed by MediaPipe)

## Installation

```bash
git clone https://github.com/Feffolino/TV-Air-Remote.git
cd TV-Air-Remote
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e .
```

On the first run the recognition model (about 8 MB) is downloaded into
`models/`.

> Do not install `opencv-python`: MediaPipe already depends on
> `opencv-contrib-python`, and having both installed breaks OpenCV.

## Configuration

1. Copy the example file:
   ```bash
   cp config.example.yaml config.yaml
   ```
2. Set the TV's IP address in `tv.host`. You can find it on the TV under
   Settings > General > Network > Network Status > IP Settings. Giving the TV a
   fixed IP address in your router is a good idea.
3. Optional, to turn the TV on with a gesture: set the TV's MAC address in
   `tv.mac` and enable Settings > General > Network > Expert Settings >
   Power On with Mobile on the TV.
4. Optional: set `ui.language` to `it` for the Italian on-screen interface
   (the default is `en`).

`config.yaml` holds your network details and is ignored by git.

### First connection

On the first run the TV asks whether to allow "TV Air Remote": accept with the
remote. The permission is stored in `.tv_token` and will not be asked again.

If you denied it by mistake: Settings > General > External Device Manager >
Device Connection Manager, then allow "TV Air Remote".

## Usage

```bash
python -m tv_air_remote              # uses config.yaml
python -m tv_air_remote --dry-run    # try the gestures without touching the TV
python -m tv_air_remote --camera 1   # use another webcam
python -m tv_air_remote --lang it    # Italian on-screen interface
```

A window opens with the webcam image, the tracked hands, the current mode, the
recognised gesture, the last key sent, the TV status and the list of commands
available in the current mode. Press `q` or `ESC` to quit.

On Windows, `quick-tests.bat` opens a menu with the most common runs: dry run,
TV connection check, Wake-on-LAN, full run and the automated tests.

## Gestures

The mode depends on how many hands the webcam sees: **one hand = TV mode**,
**two hands = Navigation mode**. Navigation starts after 0.4 s with two hands
and ends after 1.5 s with a single hand, so a hand lost for a moment does not
change mode.

### The palm joystick

Hold your **open palm** still for about 0.3 s: that point becomes the centre
(a grey square on screen). Move the palm a little up, down, left or right: the
command is sent at once and, if you stay there, it repeats. The further you
move from the centre, the faster it repeats: about every 0.7 s just past the
square, down to every 0.15 s further out. Back at the centre it stops; going
straight from right to left switches direction immediately. Moving
diagonally keeps the direction you started with.

With **two hands in Navigation mode** each hand has its own joystick: the hand
on the left of the image moves left, up and down, the hand on the right moves
right, up and down. Moving a hand towards the other one does nothing, and up
or down done with both hands counts once. If the webcam loses one of the two
hands, the remaining one handles every direction. A hand lost for less than
1.5 s keeps its centre.

### TV mode (one hand)

| Gesture | Command |
|---|---|
| Palm up / down | volume + / − (repeats while held, faster further out) |
| Palm right / left | next / previous channel |
| Close and reopen your hand (click) | OK, which pauses and resumes videos |
| Thumb up / down (held) | volume + / − (alternative to the palm) |
| Fist, held for 1 s | Home |
| 🤟 (thumb, index and pinky), held for 1.5 s | power on / off |

### Navigation mode (two hands)

| Gesture | Command |
|---|---|
| Palm up / down / left / right | arrow keys |
| Close and reopen your hand (click) | OK |
| Thumb up | OK (alternative to the click) |
| Thumb pointing left, other fingers closed | back |
| Victory ✌ | back (alternative) |
| Thumb down | volume − |
| 🤟 held for 1.5 s | power on / off |

Holding a fist does nothing in this mode.

A single command (fist, 🤟, OK, back) fires once: to repeat it, release the
gesture for at least half a second.

The thumb pointing left is recognised from the shape of the hand rather than
from MediaPipe's labels, which have no such gesture. Thumb up, thumb down and
victory rely on MediaPipe's labels and can be unreliable with some webcams or
lighting: the palm, the click, the fist and the thumb pointing left are the
most dependable gestures.

Every mapping and threshold can be changed in the `mapping` and `thresholds`
sections of `config.yaml`.

## Tips

- Stay 1–3 metres from the webcam, with your hands clearly visible and not
  against a bright window.
- Make gestures calmly: a gesture counts after about 0.2 s of stability.
- If a gesture is hard to trigger, lower `thresholds.min_score` slightly (for
  example 0.6); if you get unwanted commands, raise it.
- If tiny movements of the palm trigger commands, raise `thresholds.palm_zone`;
  if you have to move it too much, lower it.

## Dry-run checklist

Run `python -m tv_air_remote --dry-run` and check that the terminal shows the
expected key:

- [ ] One hand: palm still, then moved up → `KEY_VOLUP`; down → `KEY_VOLDOWN`
- [ ] One hand: palm right → `KEY_CHUP`; left → `KEY_CHDOWN`
- [ ] Palm held up → `KEY_VOLUP` repeated; back at the centre → it stops
- [ ] Palm moved diagonally → the starting direction is kept, no alternating
- [ ] A hand moving without stopping first → no key
- [ ] Thumb up held for 3 s → `KEY_VOLUP` repeated, faster after 1.5 s
- [ ] Click during a video (YouTube, Netflix…) → `KEY_ENTER`, the video pauses
- [ ] 🤟 for less than 1.5 s → no key; for longer → `KEY_POWER`
- [ ] Fist for 1 s → `KEY_HOME` once, even when kept closed
- [ ] Palm closed and reopened quickly → `KEY_ENTER`, in both modes
- [ ] Second hand in view → `Mode -> nav` in the log and "Navigation" on screen
- [ ] Navigation: left hand to the left → `KEY_LEFT`, right hand to the right →
      `KEY_RIGHT`, either hand up/down → `KEY_UP`/`KEY_DOWN`; hands towards each
      other → no key; thumb pointing left → `KEY_RETURN` (not Home, not a click)
- [ ] Palm just past the square → slow arrows; further out → fast arrows
- [ ] Second hand removed → `Mode -> tv`

## Troubleshooting

| Problem | Solution |
|---|---|
| "TV: not connected" on screen | Check the IP address and that the computer and the TV are on the same network. The program retries by itself. |
| "access denied" on screen | Allow the device again (see *First connection*), then restart. |
| The TV does not turn on with 🤟 | `tv.mac` must be set and Power On with Mobile enabled on the TV. |
| "Cannot open the webcam" | Close other apps using it, or try `--camera 1`. |
| Slow start on Windows | The webcam is opened with DirectShow; if it fails, the program falls back to the default backend, which can take 10–30 s. |
| "Not available" when pausing a live channel | Samsung timeshift often needs a USB stick plugged into the TV. In video apps pausing with the click works. |
| The left arrow rewinds a video by 10 s | That is what Samsung video apps do with the left arrow during playback, exactly as with the remote. |
| The model cannot be downloaded | Download the URL shown in the message by hand and save it as `models/gesture_recognizer.task`. |

## How it works

1. `camera.py` grabs mirrored frames from the webcam, so your left is the
   left of the image.
2. `recognizer.py` runs MediaPipe's Gesture Recognizer on up to two hands.
3. `interpreter.py` turns the hands into keys: it picks the mode from the
   number of hands, runs one palm joystick per hand (`joystick.py`) and detects
   clicks, held gestures and the thumb pointing left.
4. `tv.py` sends the keys to the TV in a background thread through
   [samsungtvws](https://github.com/xchwarze/samsung-tv-ws-api), reconnects
   when the TV drops the connection and resends the key that failed.
5. `overlay.py` draws the hands, the joysticks, the status and the command
   legend, with texts from `i18n.py`.

## Development

```bash
pip install -e ".[dev]"
pytest
```

The interpreter and the joystick are pure state machines that receive time
from outside, so they are tested without a webcam or a TV.

| File | Role |
|---|---|
| `tv_air_remote/config.py` | configuration and validation |
| `tv_air_remote/camera.py` | webcam capture |
| `tv_air_remote/recognizer.py` | MediaPipe Gesture Recognizer |
| `tv_air_remote/joystick.py` | open palm as a joystick, hand-shape checks |
| `tv_air_remote/interpreter.py` | state machine: hands → keys |
| `tv_air_remote/tv.py` | TV connection, reconnection, Wake-on-LAN |
| `tv_air_remote/overlay.py` | on-screen information |
| `tv_air_remote/i18n.py` | on-screen texts in English and Italian |
| `tv_air_remote/__main__.py` | startup and main loop |
| `scripts/tv_check.py` | TV connection check without a webcam |
| `quick-tests.bat` | Windows menu of common runs |

To add a language, add a block to `TEXTS` in `tv_air_remote/i18n.py` with the
same keys as `en`; a test checks that no text is missing.

## License

[MIT](LICENSE) © 2026 Stefano Manca
