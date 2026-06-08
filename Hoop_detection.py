import cv2
import numpy as np

# ---- Known dimensions of the rectangular marker (meters) ----
# Example: basketball backboard ~1.8m x 1.05m
WIDTH = 1.8
HEIGHT = 1.05

# 3D coordinates of rectangle corners in real world
object_points = np.array([
    [-WIDTH/2, -HEIGHT/2, 0],
    [ WIDTH/2, -HEIGHT/2, 0],
    [ WIDTH/2,  HEIGHT/2, 0],
    [-WIDTH/2,  HEIGHT/2, 0]
], dtype=np.float32)

# ---- Camera Calibration (example values) ----
# You should ideally calibrate your camera
camera_matrix = np.array([
    [800, 0, 320],
    [0, 800, 240],
    [0, 0, 1]
], dtype=np.float32)

dist_coeffs = np.zeros((4,1))  # assume no distortion

cap = cv2.VideoCapture(0)

while True:

    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Edge detection
    edges = cv2.Canny(gray, 50, 150)

    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:

        epsilon = 0.02 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)

        # Detect rectangles
        if len(approx) == 4 and cv2.contourArea(cnt) > 500:

            pts = approx.reshape(4,2)

            # Sort corners
            pts = pts[np.argsort(pts[:,0])]

            image_points = np.array(pts, dtype=np.float32)

            # Solve PnP
            success, rvec, tvec = cv2.solvePnP(
                object_points,
                image_points,
                camera_matrix,
                dist_coeffs
            )

            if success:

                x = tvec[0][0]
                y = tvec[1][0]
                z = tvec[2][0]

                cv2.drawContours(frame, [approx], -1, (0,255,0), 3)

                text = f"X:{x:.2f}m Y:{y:.2f}m Z:{z:.2f}m"
                cv2.putText(frame, text, (20,40),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1, (0,255,0), 2)

    cv2.imshow("Pose Estimation", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()