"""
colour_tuner.py
---------------
Interactive HSV trackbar tool.
Run this FIRST to dial in the exact orange HSV range for YOUR lighting.
Once happy, copy the printed values into hoop_detector.py.

Usage:  python colour_tuner.py
"""

import cv2
import numpy as np
from hoop_detector import CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT


def nothing(_): pass


def main():
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    cv2.namedWindow("Mask Tuner", cv2.WINDOW_NORMAL)
    cv2.createTrackbar("H low",  "Mask Tuner", 5,   179, nothing)
    cv2.createTrackbar("H high", "Mask Tuner", 20,  179, nothing)
    cv2.createTrackbar("S low",  "Mask Tuner", 120, 255, nothing)
    cv2.createTrackbar("S high", "Mask Tuner", 255, 255, nothing)
    cv2.createTrackbar("V low",  "Mask Tuner", 120, 255, nothing)
    cv2.createTrackbar("V high", "Mask Tuner", 255, 255, nothing)

    print("Adjust trackbars until only the hoop rim is white in the mask.")
    print("Press S to save values, Q to quit.\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        hl = cv2.getTrackbarPos("H low",  "Mask Tuner")
        hh = cv2.getTrackbarPos("H high", "Mask Tuner")
        sl = cv2.getTrackbarPos("S low",  "Mask Tuner")
        sh = cv2.getTrackbarPos("S high", "Mask Tuner")
        vl = cv2.getTrackbarPos("V low",  "Mask Tuner")
        vh = cv2.getTrackbarPos("V high", "Mask Tuner")

        hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv,
                           np.array([hl, sl, vl]),
                           np.array([hh, sh, vh]))
        result = cv2.bitwise_and(frame, frame, mask=mask)

        combined = np.hstack([frame, cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR), result])
        cv2.imshow("Mask Tuner", combined)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        if key == ord('s'):
            print("─── Copy these into hoop_detector.py ───────────────")
            print(f"HSV_LOWER_ORANGE = np.array([{hl}, {sl}, {vl}])")
            print(f"HSV_UPPER_ORANGE = np.array([{hh}, {sh}, {vh}])")
            print("────────────────────────────────────────────────────")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
