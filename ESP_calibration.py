"""
calibrate.py — run this ONCE to find your correct FOCAL_LENGTH_PX
"""
import cv2, numpy as np, requests

ESP32_IP   = "10.178.33.244"
STREAM_URL = f"http://{ESP32_IP}/stream"

KNOWN_DISTANCE_M  = 0.60  # hold target exactly 1 foot away
KNOWN_WIDTH_M     = 0.12    # your RECT_REAL_WIDTH_M — measure your actual target!

def stream_frames(url):
    resp = requests.get(url, stream=True, timeout=(10, None))
    buf  = b""
    for chunk in resp.iter_content(chunk_size=4096):
        buf += chunk
        start = buf.find(b'\xff\xd8')
        end   = buf.find(b'\xff\xd9')
        if start != -1 and end != -1 and end > start:
            jpg = buf[start:end+2]
            buf = buf[end+2:]
            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is not None:
                yield frame

print("=== CALIBRATION MODE ===")
print(f"Hold target at exactly {KNOWN_DISTANCE_M*100:.0f} cm ({KNOWN_DISTANCE_M*3.281:.1f} ft)")
print("Press S to sample width, Q to quit\n")

for frame in stream_frames(STREAM_URL):
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5,5), 0)
    med     = np.median(blurred)
    edges   = cv2.Canny(blurred, int(0.66*med), int(1.33*med))
    kernel  = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
    edges   = cv2.dilate(edges, kernel, iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 50: continue
        peri   = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02*peri, True)
        if len(approx) != 4: continue
        if not cv2.isContourConvex(approx): continue
        x, y, w, h = cv2.boundingRect(approx)
        if w < 10 or h < 10: continue
        if not (1.2 <= w/float(h) <= 2): continue
        if best is None or area > best[0]:
            best = (area, w, x, y)

    vis = frame.copy()
    if best:
        _, w_px, x, y = best
        focal = (w_px * KNOWN_DISTANCE_M) / KNOWN_WIDTH_M
        cv2.rectangle(vis, (x, y), (x+int(w_px), y+50), (0,255,0), 2)
        cv2.putText(vis, f"w_px = {w_px:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
        cv2.putText(vis, f"FOCAL = {focal:.1f}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)
        print(f"\r  w_px={w_px:.1f}  →  FOCAL_LENGTH_PX = {focal:.1f}    ", end="")

    cv2.imshow("Calibration", vis)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('s') and best:
        _, w_px, _, _ = best
        focal = (w_px * KNOWN_DISTANCE_M) / KNOWN_WIDTH_M
        print(f"\n\n✅ RESULT: FOCAL_LENGTH_PX = {focal:.1f}")
        print(f"   Update this in hoop_detector_esp32.py")
        break
    if key == ord('q'):
        break

cv2.destroyAllWindows()