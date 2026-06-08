"""
physics_engine.py
-----------------
2-D projectile motion solver for the basketball shooter.

Coordinate system
  Origin  → launch point (front of flywheel)
  X axis  → horizontal, towards the hoop
  Y axis  → vertical,   upwards

The ball leaves the flywheel at angle LAUNCH_ANGLE_DEG above horizontal
with speed  v0  (m/s).  We solve for the v0 that lands the ball at the
hoop given:
    - horizontal distance  Δx  (metres)
    - height difference    Δy  = hoop_height - launch_height  (metres)

Projectile equations (no air resistance):
    x(t) = v0 * cos(θ) * t
    y(t) = v0 * sin(θ) * t  - ½ g t²

Solving for v0:
    From x:  t = Δx / (v0 * cos θ)
    Sub into y:
    Δy = Δx * tan θ  -  (g * Δx²) / (2 * v0² * cos²θ)

    =>  v0² = (g * Δx²) / (2 * cos²θ * (Δx * tan θ - Δy))
    =>  v0  = sqrt( g * Δx² / (2 * cos²θ * (Δx * tan θ - Δy)) )
"""

import math
import matplotlib.pyplot as plt

# ── Physical constants ────────────────────────────────────────────────────────
G                   = 9.81       # m/s²
LAUNCH_ANGLE_DEG    = 45.0       # degrees above horizontal  ← tune for your shooter
LAUNCH_HEIGHT_M     = 0.20       # height of flywheel exit above ground (metres)
HOOP_HEIGHT_M       = 0.8       # standard NBA hoop height (metres)
BALL_RADIUS_M       = 0.033      # tennis ball radius (metres) — used for clearance check

# Flywheel → ball speed conversion
# v_ball = FLYWHEEL_EFFICIENCY * v_wheel_surface
# v_wheel_surface = π * d_wheel * RPM / 60
FLYWHEEL_DIAMETER_M = 0.10       # flywheel diameter (metres) — adjust to your build
FLYWHEEL_EFFICIENCY = 0.85       # empirical grip/slip factor  (0 – 1)
MAX_FLYWHEEL_RPM    = 6000       # safety cap


# ─────────────────────────────────────────────────────────────────────────────
class ShotSolution:
    """Carries the full solution for one shot."""
    def __init__(self, distance_m: float, v0: float, rpm: int,
                 flight_time: float, apex_height: float, valid: bool,
                 reason: str = ""):
        self.distance_m   = distance_m
        self.v0           = v0           # m/s
        self.rpm          = rpm          # flywheel RPM
        self.flight_time  = flight_time  # seconds
        self.apex_height  = apex_height  # metres (above ground)
        self.valid        = valid
        self.reason       = reason       # why invalid, if so

    def __repr__(self):
        if self.valid:
            return (f"ShotSolution(dist={self.distance_m:.2f}m  "
                    f"v0={self.v0:.2f}m/s  RPM={self.rpm}  "
                    f"t={self.flight_time:.3f}s  apex={self.apex_height:.2f}m)")
        return f"ShotSolution(INVALID: {self.reason})"


# ─────────────────────────────────────────────────────────────────────────────
def solve_shot(distance_m: float,
               launch_angle_deg: float = LAUNCH_ANGLE_DEG,
               launch_height_m:  float = LAUNCH_HEIGHT_M,
               hoop_height_m:    float = HOOP_HEIGHT_M) -> ShotSolution:
    """
    Given horizontal distance to hoop, return required v0 and flywheel RPM.

    Parameters
    ----------
    distance_m       : horizontal distance from launcher to hoop centre (m)
    launch_angle_deg : launch angle above horizontal (degrees)
    launch_height_m  : height of launch point (m)
    hoop_height_m    : height of hoop centre (m)

    Returns
    -------
    ShotSolution object
    """
    theta   = math.radians(launch_angle_deg)
    delta_y = hoop_height_m - launch_height_m     # height to clear

    # ── Physics check: angle must allow ball to reach the hoop ───────────────
    denominator = distance_m * math.tan(theta) - delta_y
    if denominator <= 0:
        return ShotSolution(distance_m, 0, 0, 0, 0, False,
                            f"Angle {launch_angle_deg}° cannot reach hoop at this distance/height")

    # ── Solve for v0 ─────────────────────────────────────────────────────────
    v0_sq = (G * distance_m**2) / (2 * math.cos(theta)**2 * denominator)
    v0    = math.sqrt(v0_sq)

    # ── Flight time ──────────────────────────────────────────────────────────
    t_flight = distance_m / (v0 * math.cos(theta))

    # ── Apex height ──────────────────────────────────────────────────────────
    t_apex   = (v0 * math.sin(theta)) / G
    apex_h   = launch_height_m + v0 * math.sin(theta) * t_apex - 0.5 * G * t_apex**2

    # ── Convert v0 to flywheel RPM ───────────────────────────────────────────
    # v_surface = v_ball / efficiency
    v_wheel_surface = v0 / FLYWHEEL_EFFICIENCY
    # RPM = (v_surface / (π * d)) * 60
    rpm = int((v_wheel_surface / (math.pi * FLYWHEEL_DIAMETER_M)) * 60)

    if rpm > MAX_FLYWHEEL_RPM:
        return ShotSolution(distance_m, v0, rpm, t_flight, apex_h, False,
                            f"Required RPM {rpm} exceeds MAX {MAX_FLYWHEEL_RPM}")

    return ShotSolution(distance_m, v0, rpm, t_flight, apex_h, True)


def rpm_to_pwm_duty(rpm: int, max_rpm: int = MAX_FLYWHEEL_RPM,
                    min_duty: float = 0.0, max_duty: float = 1.0) -> float:
    """
    Linear mapping:  RPM → PWM duty cycle  (0.0 – 1.0)
    Adjust min_duty if your ESC/motor needs a non-zero floor.
    """
    rpm_clamped = max(0, min(rpm, max_rpm))
    return min_duty + (rpm_clamped / max_rpm) * (max_duty - min_duty)


def trajectory_points(v0: float, launch_angle_deg: float = LAUNCH_ANGLE_DEG,
                      launch_height_m: float = LAUNCH_HEIGHT_M,
                      steps: int = 100) -> list[tuple[float, float]]:
    """
    Return a list of (x, y) points for the trajectory arc.
    Useful for visualisation / debugging.
    """
    theta  = math.radians(launch_angle_deg)
    vx, vy = v0 * math.cos(theta), v0 * math.sin(theta)
    points = []
    for i in range(steps + 1):
        t = i * (2 * vy / G) / steps          # 0 → time of landing
        x = vx * t
        y = launch_height_m + vy * t - 0.5 * G * t**2
        if y < 0:
            break
        points.append((x, y))
    return points


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 60)
    print("  Basketball Shooter — Physics Solver Test")
    print("=" * 60)
    print(f"  Launch angle : {LAUNCH_ANGLE_DEG}°")
    print(f"  Launch height: {LAUNCH_HEIGHT_M} m")
    print(f"  Hoop height  : {HOOP_HEIGHT_M} m")
    print(f"  Flywheel Ø   : {FLYWHEEL_DIAMETER_M*100:.0f} cm")
    print()
    print(f"  {'Dist (m)':<10} {'v0 (m/s)':<12} {'RPM':<8} {'Flight(s)':<12} {'Apex(m)':<10} {'Valid'}")
    print("  " + "-"*58)
    for d in [ 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0]:
        sol = solve_shot(d)
        status = "✓" if sol.valid else f"✗  {sol.reason}"
        print(f"  {d:<10.1f} {sol.v0:<12.2f} {sol.rpm:<8} "
              f"{sol.flight_time:<12.3f} {sol.apex_height:<10.2f} {status}")
        
        # ── Plot trajectory for a sample distance ───────────────────────────────
    test_distance = 6.0
    sol = solve_shot(test_distance)

    if sol.valid:
        pts = trajectory_points(sol.v0)

        x_vals = [p[0] for p in pts]
        y_vals = [p[1] for p in pts]

        plt.figure()
        plt.plot(x_vals, y_vals, label="Ball Trajectory")

        # Hoop position
        plt.scatter([test_distance], [HOOP_HEIGHT_M], marker='o', label="Hoop")

        # Launch point
        plt.scatter([0], [LAUNCH_HEIGHT_M], marker='o', label="Launcher")

        plt.xlabel("Horizontal Distance (m)")
        plt.ylabel("Height (m)")
        plt.title(f"Projectile Trajectory to Hoop ({test_distance} m)")
        plt.legend()
        plt.grid()

        plt.show()
