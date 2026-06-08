"""
shooter_controller.py
---------------------
Controls all physical hardware on the Raspberry Pi:
  1. Drive motors  → rotate bot to align with hoop  (angle_x → 0)
  2. Servo         → load ball into flywheel channel
  3. Flywheel ESC  → spin up to calculated RPM, hold, fire

Pin layout (BCM numbering) — change to match your wiring:
  ┌──────────────────────────────────────────────────┐
  │  LEFT  motor PWM      GPIO 12  (PWM0)            │
  │  RIGHT motor PWM      GPIO 13  (PWM1)            │
  │  LEFT  motor DIR      GPIO 20                    │
  │  RIGHT motor DIR      GPIO 21                    │
  │  Flywheel ESC PWM     GPIO 18  (HW PWM)          │
  │  Loader servo PWM     GPIO 19                    │
  └──────────────────────────────────────────────────┘

Requires:  pigpio  daemon running  (`sudo pigpio`)
           pip install pigpio
"""

import time
import math
import pigpio                        # hardware-accurate PWM on Pi

# ── GPIO pin map  (BCM) ──────────────────────────────────────────────────────
PIN_MOTOR_L_PWM  = 12
PIN_MOTOR_R_PWM  = 13
PIN_MOTOR_L_DIR  = 20
PIN_MOTOR_R_DIR  = 21
PIN_FLYWHEEL_PWM = 18               # hardware PWM → smooth ESC signal
PIN_LOADER_SERVO = 19

# ── Drive motor settings ──────────────────────────────────────────────────────
MOTOR_PWM_FREQ   = 1000             # Hz
MOTOR_MAX_DUTY   = 255              # pigpio 0-255 range

# ── Servo (loader) settings ───────────────────────────────────────────────────
SERVO_FREQ       = 50               # 50 Hz standard servo
SERVO_LOAD_US    = 1200             # pulse width µs → "load" position
SERVO_HOME_US    = 1700             # pulse width µs → "home" / retracted
SERVO_FIRE_US    = 700              # pulse width µs → push ball in

# ── Flywheel ESC (standard hobby ESC via PWM) ─────────────────────────────────
ESC_FREQ         = 50               # 50 Hz
ESC_MIN_US       = 1000             # full stop / arming pulse
ESC_MAX_US       = 2000             # full throttle
ESC_SPINUP_S     = 1.5              # seconds to let flywheel reach target RPM
MAX_FLYWHEEL_RPM = 6000             # must match physics_engine.py

# ── Alignment PID tuning ──────────────────────────────────────────────────────
ALIGN_KP         = 4.0              # proportional gain (duty / degree)
ALIGN_KI         = 0.05
ALIGN_KD         = 1.0
ALIGN_TOLERANCE  = 2.0              # degrees — "close enough" threshold
ALIGN_TIMEOUT    = 8.0              # seconds max alignment time


# ─────────────────────────────────────────────────────────────────────────────
class ShooterController:
    def __init__(self):
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise RuntimeError("Cannot connect to pigpio daemon. "
                               "Run: sudo pigpiod")

        # Set up pins
        for pin in (PIN_MOTOR_L_PWM, PIN_MOTOR_R_PWM,
                    PIN_MOTOR_L_DIR, PIN_MOTOR_R_DIR,
                    PIN_FLYWHEEL_PWM, PIN_LOADER_SERVO):
            self.pi.set_mode(pin, pigpio.OUTPUT)

        # ESC arming sequence
        self._esc_arm()
        # Loader to home
        self._servo_set(PIN_LOADER_SERVO, SERVO_HOME_US)
        time.sleep(0.5)

        print("[CTRL] ShooterController initialised")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _motor_set(self, left_speed: float, right_speed: float):
        """
        Set drive motors.
        speed: -1.0 (full reverse) → +1.0 (full forward)
        """
        for speed, pin_pwm, pin_dir in [
            (left_speed,  PIN_MOTOR_L_PWM, PIN_MOTOR_L_DIR),
            (right_speed, PIN_MOTOR_R_PWM, PIN_MOTOR_R_DIR),
        ]:
            direction = 1 if speed >= 0 else 0
            duty      = int(abs(speed) * MOTOR_MAX_DUTY)
            self.pi.write(pin_dir, direction)
            self.pi.set_PWM_dutycycle(pin_pwm, duty)
            self.pi.set_PWM_frequency(pin_pwm, MOTOR_PWM_FREQ)

    def _motor_stop(self):
        self._motor_set(0.0, 0.0)

    def _servo_set(self, pin: int, pulse_us: int):
        self.pi.set_servo_pulsewidth(pin, pulse_us)

    def _esc_arm(self):
        """Send 1 s arming pulse to ESC."""
        print("[CTRL] Arming ESC …")
        self.pi.set_servo_pulsewidth(PIN_FLYWHEEL_PWM, ESC_MIN_US)
        time.sleep(1.0)
        print("[CTRL] ESC armed")

    def _rpm_to_esc_us(self, rpm: int) -> int:
        """Linear interpolation: RPM → ESC pulse width µs."""
        ratio = max(0.0, min(1.0, rpm / MAX_FLYWHEEL_RPM))
        return int(ESC_MIN_US + ratio * (ESC_MAX_US - ESC_MIN_US))

    # ── Public API ────────────────────────────────────────────────────────────

    def align_to_hoop(self, get_angle_fn) -> bool:
        """
        Rotate the bot until angle_x ≈ 0.
        get_angle_fn : callable → float  (current horizontal offset in degrees)
                       should return None if hoop not visible

        Uses a PD controller on the drive motors (tank-turn in place).

        Returns True if aligned, False if timeout / lost hoop.
        """
        print("[ALIGN] Starting alignment …")
        integral = 0.0
        prev_err = 0.0
        t_start  = time.time()
        dt       = 0.05  # 20 Hz control loop

        while True:
            angle = get_angle_fn()
            if angle is None:
                print("[ALIGN] ⚠ Hoop lost during alignment")
                self._motor_stop()
                return False

            error    = angle          # +ve = hoop is right → rotate CW
            integral += error * dt
            deriv    = (error - prev_err) / dt
            output   = ALIGN_KP * error + ALIGN_KI * integral + ALIGN_KD * deriv
            output   = max(-1.0, min(1.0, output / 90.0))   # normalise to [-1,1]
            prev_err = error

            if abs(error) < ALIGN_TOLERANCE:
                self._motor_stop()
                print(f"[ALIGN] ✓ Aligned  (error={error:.2f}°)")
                return True

            if time.time() - t_start > ALIGN_TIMEOUT:
                self._motor_stop()
                print("[ALIGN] ✗ Timeout")
                return False

            # Tank turn: left forward, right backward (or vice versa)
            self._motor_set( output, -output)
            time.sleep(dt)

    def spinup_flywheel(self, rpm: int):
        """Spin flywheel to target RPM and wait for it to spool up."""
        esc_us = self._rpm_to_esc_us(rpm)
        print(f"[SHOOT] Spinning up flywheel → {rpm} RPM  (ESC pulse {esc_us} µs)")
        self.pi.set_servo_pulsewidth(PIN_FLYWHEEL_PWM, esc_us)
        time.sleep(ESC_SPINUP_S)
        print(f"[SHOOT] Flywheel at target RPM")

    def load_ball(self):
        """Move loader servo to 'load' position, then retract."""
        print("[SHOOT] Loading ball …")
        self._servo_set(PIN_LOADER_SERVO, SERVO_LOAD_US)
        time.sleep(0.6)
        self._servo_set(PIN_LOADER_SERVO, SERVO_HOME_US)
        time.sleep(0.4)

    def fire(self):
        """Push ball through flywheel."""
        print("[SHOOT] FIRE!")
        self._servo_set(PIN_LOADER_SERVO, SERVO_FIRE_US)
        time.sleep(0.5)
        self._servo_set(PIN_LOADER_SERVO, SERVO_HOME_US)
        time.sleep(0.3)

    def spindown_flywheel(self):
        """Safely return flywheel to idle."""
        print("[SHOOT] Spinning down flywheel …")
        self.pi.set_servo_pulsewidth(PIN_FLYWHEEL_PWM, ESC_MIN_US)
        time.sleep(0.5)

    def shoot_sequence(self, rpm: int):
        """
        Full shoot sequence:
          1. Spin up flywheel
          2. Load ball
          3. Fire
          4. Spin down
        """
        self.spinup_flywheel(rpm)
        self.load_ball()
        self.fire()
        time.sleep(0.3)
        self.spindown_flywheel()
        print("[SHOOT] Sequence complete")

    def cleanup(self):
        """Release all GPIO resources."""
        self._motor_stop()
        self.spindown_flywheel()
        self.pi.set_servo_pulsewidth(PIN_LOADER_SERVO, 0)
        self.pi.stop()
        print("[CTRL] GPIO cleaned up")


# ── Standalone test (no hardware — prints what would happen) ──────────────────
if __name__ == '__main__':
    print("[TEST] ShooterController — dry-run checks")
    print()

    # Simulate ESC pulse mapping
    print("  RPM → ESC pulse width:")
    for rpm in [0, 1000, 2000, 3000, 4000, 5000, 6000]:
        ratio = max(0.0, min(1.0, rpm / MAX_FLYWHEEL_RPM))
        us = int(ESC_MIN_US + ratio * (ESC_MAX_US - ESC_MIN_US))
        print(f"    {rpm:5d} RPM  →  {us} µs")

    print()
    print("[TEST] Servo positions:")
    print(f"  Home  : {SERVO_HOME_US} µs")
    print(f"  Load  : {SERVO_LOAD_US} µs")
    print(f"  Fire  : {SERVO_FIRE_US} µs")
    print()
    print("[TEST] To run on real hardware, ensure pigpiod is running:")
    print("  sudo pigpiod")
    print("  python shooter_controller.py")
