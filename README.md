# 🏀 Basketball Shooter Bot — Raspberry Pi

Autonomous camera-guided basketball shooter with:
- OpenCV hoop detection (colour + ellipse fitting)
- 2D projectile physics solver (RPM from distance)
- PID alignment via drive motors
- Servo ball loader + flywheel shooter

---

## File Overview

```
scripts/
  hoop_detector.py      ← Camera → distance & angle to hoop
  physics_engine.py     ← Solve required flywheel RPM from distance
  shooter_controller.py ← GPIO: motors, servo, flywheel ESC
  main.py               ← Full pipeline orchestrator
  colour_tuner.py       ← Interactive HSV tuning utility
```

---

## Quickstart

### 1. Install dependencies
```bash
pip install opencv-python pigpio numpy
sudo pigpiod          # start the pigpio daemon
```

### 2. Tune HSV colour range for your hoop/lighting
```bash
python colour_tuner.py
# Adjust sliders until only the orange rim is white
# Press S to print values → paste into hoop_detector.py
```

### 3. Test detection only
```bash
python hoop_detector.py
# Shows live feed with distance + angles overlaid
```

### 4. Test physics solver
```bash
python physics_engine.py
# Prints RPM table for distances 1–6 m
```

### 5. Test hardware (no ball)
```bash
python shooter_controller.py
# Dry-run, prints what it would do
```

### 6. Full auto-shot
```bash
python main.py          # auto-detect hardware
python main.py --sim    # simulation (no GPIO)
python main.py --real   # force hardware mode
```

---

## Hardware Wiring (BCM pin numbers)

| Component        | Pin  | Notes                        |
|------------------|------|------------------------------|
| Left motor PWM   | 12   | Hardware PWM0                |
| Right motor PWM  | 13   | Hardware PWM1                |
| Left motor DIR   | 20   |                              |
| Right motor DIR  | 21   |                              |
| Flywheel ESC PWM | 18   | Hardware PWM — 50 Hz         |
| Loader servo PWM | 19   | Standard 50 Hz servo signal  |

---

## Tunable constants (one place per file)

### `hoop_detector.py`
| Constant | Default | Description |
|---|---|---|
| `HOOP_REAL_DIAMETER_M` | 0.4572 | NBA rim diameter (m) |
| `CAMERA_FOV_H_DEG` | 62.2 | Pi Cam v2 horizontal FOV |
| `HSV_LOWER/UPPER_ORANGE` | see file | Tune with colour_tuner.py |

### `physics_engine.py`
| Constant | Default | Description |
|---|---|---|
| `LAUNCH_ANGLE_DEG` | 45° | Adjust to your shooter geometry |
| `LAUNCH_HEIGHT_M` | 0.80 m | Height of flywheel exit |
| `FLYWHEEL_DIAMETER_M` | 0.10 m | Your flywheel diameter |
| `FLYWHEEL_EFFICIENCY` | 0.85 | Grip/slip factor |

### `shooter_controller.py`
| Constant | Default | Description |
|---|---|---|
| `SERVO_LOAD_US` | 1200 µs | Servo "load" pulse |
| `SERVO_FIRE_US` | 700 µs | Servo "fire" push pulse |
| `ESC_SPINUP_S` | 1.5 s | Flywheel spool-up wait time |

---

## Shot Pipeline

```
Camera detects hoop (5 consecutive frames)
         │
         ▼
Physics solver → required RPM
         │
         ▼
PID motor loop → align bot (angle_x → 0°)
         │
         ▼
Re-detect distance post-movement
         │
         ▼
Spinup flywheel → Load ball → Fire → Spindown
```
