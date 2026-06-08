"""
hoop_detector_esp32.py  — PC-side version using ESP32-CAM
"""
import cv2, numpy as np, math, time, requests, threading

# ── ESP32-CAM config ──────────────────────────────────────────────
ESP32_IP    = "10.178.33.244"
STREAM_URL  = f"http://{ESP32_IP}/stream"   # FIX 1: port 81 for CameraWebServer
CMD_URL     = f"http://{ESP32_IP}/cmd"

# ── Constants ─────────────────────────────────────────────────────
FRAME_WIDTH         = 320
FRAME_HEIGHT        = 240
FOCAL_LENGTH_PX     = 415
RECT_REAL_WIDTH_M   = 0.12
MIN_CONTOUR_AREA    = 50
h, w = frame.shape[:2]
ax, ay = calculate_angles(best['cx'], best['cy'], w, h)

# ───────────────────────────────────────q──────────────────────────
def calculate_distance(apparent_diameter_px: float) -> float:
    if apparent_diameter_px <= 0:
        return float('inf')
    return (RECT_REAL_WIDTH_M * FOCAL_LENGTH_PX) / apparent_diameter_px


def calculate_angles(cx_px: float, cy_px: float, frame_w, frame_h) -> tuple[float, float]:
    dx = cx_px - frame_w  / 2.0
    dy = frame_h / 2.0 - cy_px
    angle_x = math.degrees(math.atan2(dx, FOCAL_LENGTH_PX))
    angle_y = math.degrees(math.atan2(dy, FOCAL_LENGTH_PX))
    return angle_x, angle_y


def detect_hoop(frame: np.ndarray) -> dict | None:
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    med    = np.median(blurred)
    lower  = int(max(0,   0.66 * med))
    upper  = int(min(255, 1.33 * med))
    edges  = cv2.Canny(blurred, lower, upper)

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
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

        if len(approx) != 4:
            continue
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
    ax, ay = calculate_angles(best['cx'], best['cy'], FRAME_WIDTH, FRAME_HEIGHT)

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


def draw_overlay(frame: np.ndarray, info: dict) -> np.ndarray:
    vis = frame.copy()
    h, w = vis.shape[:2]
    cx_frame, cy_frame = w // 2, h // 2

    # ── Crosshair at frame centre ─────────────────────────────────
    CROSS_SIZE  = 20
    CROSS_COLOR = (0, 255, 255)   # yellow
    CROSS_THICK = 2
    # Horizontal line with gap in middle
    cv2.line(vis, (cx_frame - CROSS_SIZE, cy_frame),
                  (cx_frame - 6,          cy_frame), CROSS_COLOR, CROSS_THICK)
    cv2.line(vis, (cx_frame + 6,          cy_frame),
                  (cx_frame + CROSS_SIZE, cy_frame), CROSS_COLOR, CROSS_THICK)
    # Vertical line with gap in middle
    cv2.line(vis, (cx_frame, cy_frame - CROSS_SIZE),
                  (cx_frame, cy_frame - 6           ), CROSS_COLOR, CROSS_THICK)
    cv2.line(vis, (cx_frame, cy_frame + 6           ),
                  (cx_frame, cy_frame + CROSS_SIZE), CROSS_COLOR, CROSS_THICK)
    # Centre dot
    cv2.circle(vis, (cx_frame, cy_frame), 3, CROSS_COLOR, -1)

    # ── If no hoop detected, just return crosshair ────────────────
    if info is None:
        cv2.putText(vis, "NO HOOP DETECTED", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        return vis

    # ── Hoop polygon + centre dot ─────────────────────────────────
    cv2.polylines(vis, [info['approx']], isClosed=True,
                  color=(0, 255, 0), thickness=2)
    hx, hy = int(info['cx']), int(info['cy'])
    cv2.circle(vis, (hx, hy), 5, (0, 0, 255), -1)

    # ── Error line: frame centre → hoop centre ────────────────────
    ax = info['angle_x_deg']
    ALIGNED = abs(ax) < 8          # same threshold as decide_command()
    line_color = (0, 255, 0) if ALIGNED else (0, 0, 255)
    cv2.line(vis, (cx_frame, cy_frame), (hx, hy), line_color, 1)

    # ── Horizontal alignment bar at bottom ────────────────────────
    # Shows how far left/right the hoop is as a sliding indicator
    BAR_Y   = h - 20
    BAR_W   = 200
    BAR_X0  = cx_frame - BAR_W // 2
    BAR_X1  = cx_frame + BAR_W // 2
    cv2.rectangle(vis, (BAR_X0, BAR_Y - 8), (BAR_X1, BAR_Y + 8),
                  (50, 50, 50), -1)                          # background
    cv2.rectangle(vis, (BAR_X0, BAR_Y - 8), (BAR_X1, BAR_Y + 8),
                  (200, 200, 200), 1)                        # border
    # Clamp indicator position within bar
    max_angle = 30.0
    norm  = max(-1.0, min(1.0, ax / max_angle))
    ind_x = int(cx_frame + norm * (BAR_W // 2))
    ind_color = (0, 255, 0) if ALIGNED else (0, 100, 255)
    cv2.rectangle(vis, (ind_x - 4, BAR_Y - 8),
                        (ind_x + 4, BAR_Y + 8), ind_color, -1)
    cv2.line(vis, (cx_frame, BAR_Y - 8),
                  (cx_frame, BAR_Y + 8), (255, 255, 0), 1)  # centre tick

    # ── Text HUD ─────────────────────────────────────────────────
    align_txt = "ALIGNED" if ALIGNED else f"{'RIGHT' if ax>0 else 'LEFT'} {abs(ax):.1f}°"
    hud = [
        f"Distance : {info['distance_m']:.2f} m",
        f"Angle X  : {info['angle_x_deg']:+.1f} deg  {align_txt}",
        f"Angle Y  : {info['angle_y_deg']:+.1f} deg",
        f"Rect W/H : {info['w_px']:.0f} / {info['h_px']:.0f} px",
    ]
    for i, txt in enumerate(hud):
        cv2.putText(vis, txt, (10, 25 + i * 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 255, 0), 2)

    return vis
# ── Non-blocking command sender ───────────────────────────────────
def send_command(cmd: str):
    def _send():
        try:
            requests.get(CMD_URL, params={"v": cmd}, timeout=0.5)
        except Exception:
            pass
    threading.Thread(target=_send, daemon=True).start()


# ── Decision logic ────────────────────────────────────────────────
def decide_command(info: dict | None) -> str:
    if info is None:
        return "STOP"
    ax   = info['angle_x_deg']
    dist = info['distance_m']
    if abs(ax) > 8:
        return "RIGHT" if ax > 0 else "LEFT"
    if dist > 1.5:
        return "FORWARD"
    return "SHOOT"


# ── FIX 2: Manual MJPEG reader (replaces cv2.VideoCapture) ───────
def stream_frames(url: str):
    """
    Generator that yields BGR frames from an ESP32-CAM MJPEG stream.
    Works where cv2.VideoCapture fails because it parses JPEG markers
    directly from the raw HTTP byte stream.
    """
    print(f"[INFO] Connecting to {url} ...")
    try:
        resp = requests.get(url, stream=True, timeout=(10, None))
    except requests.exceptions.ConnectionError:
        print(f"[ERROR] Cannot connect to {url}")
        return

    buf = b""
    for chunk in resp.iter_content(chunk_size=4096):
        buf += chunk
        while True:
            start = buf.find(b'\xff\xd8')   # JPEG SOI marker
            end   = buf.find(b'\xff\xd9')   # JPEG EOI marker
            if start == -1 or end == -1 or end < start:
                break                        # incomplete frame, read more

            jpg = buf[start:end + 2]
            buf = buf[end + 2:]              # keep remainder

            frame = cv2.imdecode(
                np.frombuffer(jpg, dtype=np.uint8),
                cv2.IMREAD_COLOR
            )
            if frame is not None:
                yield frame


# ── Main loop ─────────────────────────────────────────────────────
def main():
    last_cmd = None
    print("[INFO] Hoop detector starting — press Q to quit")

    for frame in stream_frames(STREAM_URL):
        info = detect_hoop(frame)
        cmd  = decide_command(info)

        # Only transmit when command changes (avoids flooding ESP32)
        if cmd != last_cmd:
            send_command(cmd)
            last_cmd = cmd
            print(f"[CMD] → {cmd}")

        vis = draw_overlay(frame, info) if info else frame.copy()
        if info is None:
            cv2.putText(vis, "NO HOOP DETECTED", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        cv2.imshow("Hoop Detector [ESP32]", vis)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
    print("Frame size:", frame.shape)