"""
main.py
-------
Full autonomous shot pipeline:

  ┌─────────────────────────────────────────────────────┐
  │  STEP 1: Camera detects hoop                        │
  │  STEP 2: Solve required flywheel RPM (physics)      │
  │  STEP 3: Align bot (drive motors, PID loop)         │
  │  STEP 4: Confirm detection + recalculate            │
  │  STEP 5: Shoot  (spinup → load → fire → spindown)  │
  └─────────────────────────────────────────────────────┘

Run modes
  --real     Use real camera + real GPIO   (default when pigpiod available)
  --sim      Simulation / dry-run mode     (no hardware needed)

Usage:
  python main.py          # auto-detect
  python main.py --sim    # force simulation
  python main.py --real   # force hardware
"""

import cv2
import time
import sys
import argparse
import threading

# Local modules
from hoop_detector   import detect_hoop, draw_overlay, FRAME_WIDTH, FRAME_HEIGHT, CAMERA_INDEX
from physics_engine  import solve_shot, LAUNCH_ANGLE_DEG, LAUNCH_HEIGHT_M, HOOP_HEIGHT_M

# ── Config ────────────────────────────────────────────────────────────────────
DETECTION_CONFIRM_FRAMES = 5        # consecutive frames hoop must be visible
MIN_DISTANCE_M           = 0.5     # metres — don't shoot if too close
MAX_DISTANCE_M           = 6.0     # metres — don't shoot if too far
STEADY_FRAMES_NEEDED     = 10      # frames where angle_x < tolerance before align step ends

# ── Shared state (camera thread → main thread) ────────────────────────────────
_latest_info = None
_info_lock   = threading.Lock()


def camera_thread_fn(cap):
    """Continuously reads frames and updates _latest_info."""
    global _latest_info
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        info = detect_hoop(frame)
        with _info_lock:
            _latest_info = info
        # Show live feed
        with _info_lock:
            disp_info = _latest_info
        vis = draw_overlay(frame, disp_info) if disp_info else frame
        cv2.imshow("Basketball Bot — Live", vis)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break


def get_current_angle():
    """Used by align_to_hoop as the angle callback."""
    with _info_lock:
        info = _latest_info
    return info['angle_x_deg'] if info else None


# ─────────────────────────────────────────────────────────────────────────────
def run_pipeline(sim_mode: bool = False):
    print()
    print("╔══════════════════════════════════════════╗")
    print("║   Basketball Shooter — Auto Shot v1.0   ║")
    print("╚══════════════════════════════════════════╝")
    print(f"  Mode: {'SIMULATION' if sim_mode else 'HARDWARE'}")
    print()

    # ── Init hardware (or stub) ───────────────────────────────────────────────
    if sim_mode:
        class FakeController:
            def align_to_hoop(self, fn):
                print("[SIM]  align_to_hoop() called")
                return True
            def shoot_sequence(self, rpm):
                print(f"[SIM]  shoot_sequence(rpm={rpm}) called")
            def cleanup(self):
                print("[SIM]  cleanup() called")
        ctrl = FakeController()
    else:
        from shooter_controller import ShooterController
        ctrl = ShooterController()

    # ── Open camera ───────────────────────────────────────────────────────────
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    t = threading.Thread(target=camera_thread_fn, args=(cap,), daemon=True)
    t.start()
    print("[MAIN] Camera thread started — press Q in window to abort\n")
    time.sleep(1.0)   # allow camera to warm up

    try:
        # ── STEP 1: Detect hoop ───────────────────────────────────────────────
        print("━━━  STEP 1: Locating hoop …")
        confirm_count = 0
        while confirm_count < DETECTION_CONFIRM_FRAMES:
            with _info_lock:
                info = _latest_info
            if info:
                confirm_count += 1
                print(f"  [{confirm_count}/{DETECTION_CONFIRM_FRAMES}] "
                      f"dist={info['distance_m']:.2f}m  "
                      f"ax={info['angle_x_deg']:+.1f}°")
            else:
                confirm_count = 0
                print("  Waiting for hoop …")
            time.sleep(0.1)

        with _info_lock:
            info = _latest_info

        dist = info['distance_m']
        print(f"\n✓ Hoop confirmed at {dist:.2f} m  |  "
              f"angle_x={info['angle_x_deg']:+.1f}°  "
              f"angle_y={info['angle_y_deg']:+.1f}°")

        # ── Range check ───────────────────────────────────────────────────────
        if not (MIN_DISTANCE_M <= dist <= MAX_DISTANCE_M):
            print(f"✗ Distance {dist:.2f} m out of range "
                  f"[{MIN_DISTANCE_M}–{MAX_DISTANCE_M} m]. Aborting.")
            return

        # ── STEP 2: Solve physics ─────────────────────────────────────────────
        print("\n━━━  STEP 2: Solving shot physics …")
        sol = solve_shot(dist)
        if not sol.valid:
            print(f"✗ No valid shot solution: {sol.reason}")
            return

        print(f"  Launch angle : {LAUNCH_ANGLE_DEG}°")
        print(f"  Required v0  : {sol.v0:.2f} m/s")
        print(f"  Flywheel RPM : {sol.rpm}")
        print(f"  Flight time  : {sol.flight_time:.3f} s")
        print(f"  Apex height  : {sol.apex_height:.2f} m")

        # ── STEP 3: Align bot ─────────────────────────────────────────────────
        print("\n━━━  STEP 3: Aligning bot …")
        aligned = ctrl.align_to_hoop(get_current_angle)
        if not aligned:
            print("✗ Alignment failed. Aborting.")
            return

        # ── STEP 4: Re-confirm distance after movement ────────────────────────
        print("\n━━━  STEP 4: Re-confirming aim …")
        time.sleep(0.5)
        with _info_lock:
            info2 = _latest_info

        if info2 is None:
            print("✗ Lost hoop after alignment. Aborting.")
            return

        dist2 = info2['distance_m']
        sol2  = solve_shot(dist2)
        print(f"  Updated dist : {dist2:.2f} m  "
              f"(Δ {abs(dist2-dist)*100:.1f} cm)")
        print(f"  Updated RPM  : {sol2.rpm}")

        if not sol2.valid:
            print(f"✗ Updated shot invalid: {sol2.reason}")
            return

        # ── STEP 5: SHOOT ─────────────────────────────────────────────────────
        print("\n━━━  STEP 5: SHOOTING …")
        print(f"  Flywheel RPM = {sol2.rpm}")
        ctrl.shoot_sequence(sol2.rpm)

        print("\n✅  Shot complete!\n")

    except KeyboardInterrupt:
        print("\n[MAIN] Interrupted by user")
    finally:
        ctrl.cleanup()
        cap.release()
        cv2.destroyAllWindows()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Basketball Bot Shooter')
    group  = parser.add_mutually_exclusive_group()
    group.add_argument('--sim',  action='store_true', help='Simulation mode (no GPIO)')
    group.add_argument('--real', action='store_true', help='Force real hardware mode')
    args = parser.parse_args()

    # Auto-detect: if pigpiod is available → real, else → sim
    if args.sim:
        sim = True
    elif args.real:
        sim = False
    else:
        try:
            import pigpio
            pi = pigpio.pi()
            sim = not pi.connected
            pi.stop()
        except ImportError:
            sim = True

    run_pipeline(sim_mode=sim)
