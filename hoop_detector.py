"""
hoop_detector.py
----------------
Detects the basketball hoop using the Raspberry Pi camera via OpenCV.
Returns:
  - distance  (meters)   from camera/bot to the hoop centre
  - angle_x   (degrees)  horizontal offset  (+ve = hoop is RIGHT of centre)
  - angle_y   (degrees)  vertical   offset  (+ve = hoop is ABOVE  centre)

Hardware assumptions
  - Pi Camera v2 (or USB webcam) attached to the bot
  - Camera is mounted at a fixed height (CAMERA_HEIGHT_M)
  - Standard NBA rim diameter  = 0.4572 m  (18 in)
  - Camera horizontal FOV      = 62.2 °  (Pi Cam v2 default)
"""

import cv2
import numpy as np
import math
import time

# ── Camera / physical constants ──────────────────────────────────────────────
CAMERA_INDEX        = 0          # 0 = default cam, change if using PiCamera module
FRAME_WIDTH         = 640
FRAME_HEIGHT        = 380
CAMERA_FOV_H_DEG    = 62.2       # horizontal field of view  (Pi Cam v2)
CAMERA_FOV_V_DEG    = 48.8       # vertical   field of view  (Pi Cam v2)

HOOP_REAL_DIAMETER_M = 0.4572    # NBA rim inner diameter in metres

# ── HSV colour ranges for orange hoop/rim ────────────────────────────────────
# Tune these in test_colour_tuner.py if lighting conditions differ
HSV_LOWER_ORANGE = np.array([5,  120, 120])
HSV_UPPER_ORANGE = np.array([20, 255, 255])

# ── Derived focal length (pixels) ────────────────────────────────────────────
# focal_px = (frame_width / 2) / tan(FOV_h / 2)
FOCAL_LENGTH_PX = 110.0    # calibrated: 69px at 1m with 12cm rect


# ─────────────────────────────────────────────────────────────────────────────
def calculate_distance(apparent_diameter_px: float) -> float:
    """
    Distance via pinhole model:
        D = (real_diameter * focal_length) / apparent_diameter_px
    """
    if apparent_diameter_px <= 0:
        return float('inf')
    return (RECT_REAL_WIDTH_M * FOCAL_LENGTH_PX) / apparent_diameter_px


def calculate_angles(cx_px: float, cy_px: float) -> tuple[float, float]:
 
    dx = cx_px - FRAME_WIDTH  / 2.0
    dy = FRAME_HEIGHT / 2.0 - cy_px   # invert Y so up = positive

    angle_x = math.degrees(math.atan2(dx, FOCAL_LENGTH_PX))
    angle_y = math.degrees(math.atan2(dy, FOCAL_LENGTH_PX))
    return angle_x, angle_y


# ── Physical constant update ──────────────────────────────────────────────────
# Replace HOOP_REAL_DIAMETER_M with the real width of your rectangular target




RECT_REAL_WIDTH_M = 0.12   # e.g. inner hoop width, or backboard target width
HSV_LOWER_ORANGE = np.array([0,  50,  50])   # broader low end
HSV_UPPER_ORANGE = np.array([25, 255, 255])  # broader high end

# Drop the minimum contour area — at 7ft a small drawn rect won't be huge
MIN_CONTOUR_AREA = 50



def detect_hoop(frame: np.ndarray) -> dict | None:



    




    """
    Edge-based rectangle detector — works on ANY color rectangle.
    No HSV tuning needed.
    """
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Auto-threshold Canny using median brightness
    med    = np.median(blurred)
    lower  = int(max(0,   0.66 * med))
    upper  = int(min(255, 1.33 * med))
    edges  = cv2.Canny(blurred, lower, upper)

    # Dilate edges slightly to close small gaps in drawn lines
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges  = cv2.dilate(edges, kernel, iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    best = None
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < MIN_CONTOUR_AREA:
            continue

        peri   = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)  # 0.02 = looser fit

        if len(approx) != 4:
            continue

        # Confirm it's convex (rules out weird shapes that happen to have 4 pts)
        if not cv2.isContourConvex(approx):
            continue

        x, y, w, h = cv2.boundingRect(approx)
        if w < 10 or h < 10:
            continue

        aspect = w / float(h)
        if not (1.2 <= aspect <= 2):
            continue

        if best is None or area > best['area']:
            best = {
                'approx' : approx,
                'area'   : area,
                'cx'     : x + w / 2.0,
                'cy'     : y + h / 2.0,
                'w_px'   : float(w),
                'h_px'   : float(h),
                'rect'   : (x, y, w, h),
            }

    if best is None:
        return None

    dist   = calculate_distance(best['w_px'])
    ax, ay = calculate_angles(best['cx'], best['cy'])

    return {
        'cx'          : best['cx'],
        'cy'          : best['cy'],
        'w_px'        : best['w_px'],
        'h_px'        : best['h_px'],
        'distance_m'  : dist,
        'angle_x_deg' : ax,
        'angle_y_deg' : ay,
        'approx'      : best['approx'],
        'rect'        : best['rect'],
    }




# ── Visual overlay helper ─────────────────────────────────────────────────────
def draw_overlay(frame: np.ndarray, info: dict) -> np.ndarray:
    vis = frame.copy()

    # Draw the 4-point polygon
    cv2.polylines(vis, [info['approx']], isClosed=True, color=(0, 255, 0), thickness=2)

    cx, cy = int(info['cx']), int(info['cy'])
    cv2.circle(vis, (cx, cy), 5, (0, 0, 255), -1)

    # Crosshair at frame centre
    cv2.line(vis, (FRAME_WIDTH // 2, 0), (FRAME_WIDTH // 2, FRAME_HEIGHT), (255, 255, 0), 1)
    cv2.line(vis, (0, FRAME_HEIGHT // 2), (FRAME_WIDTH, FRAME_HEIGHT // 2), (255, 255, 0), 1)

    lines = [
        f"Distance : {info['distance_m']:.2f} m",
        f"Angle X  : {info['angle_x_deg']:+.1f} deg",
        f"Angle Y  : {info['angle_y_deg']:+.1f} deg",
        f"Rect W/H : {info['w_px']:.0f} / {info['h_px']:.0f} px",
    ]
    for i, txt in enumerate(lines):
        cv2.putText(vis, txt, (10, 25 + i * 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
    return vis

# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == '__main__':

    
    
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    print("[INFO] Hoop detector running — press Q to quit")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Cannot read from camera")
            break

        info = detect_hoop(frame)
        if info:
            vis = draw_overlay(frame, info)
            print(f"w_px={info['w_px']:.1f}")

            print(f"\r[HOOP]  dist={info['distance_m']:.2f}m  "
                  f"ax={info['angle_x_deg']:+.1f}°  "
                  f"ay={info['angle_y_deg']:+.1f}°       ", end='')
        else:
            vis = frame.copy()
            cv2.putText(vis, "NO HOOP DETECTED", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            print("\r[HOOP]  -- not found --                ", end='')

        cv2.imshow("Hoop Detector", vis)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
