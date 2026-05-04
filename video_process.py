import cv2
import requests

ESP_IP = "192.168.x.x"

cap = cv2.VideoCapture(f"http://{ESP_IP}:81/stream")

last_cmd = ""

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # ===== YOUR RECTANGLE DETECTION HERE =====
    # Example placeholder:
    h, w, _ = frame.shape
    center_x = w // 2

    # Fake logic (replace with your detection)
    if center_x < w * 0.4:
        cmd = 'L'
    elif center_x > w * 0.6:
        cmd = 'R'
    else:
        cmd = 'F'

    # ===== SEND COMMAND =====
    if cmd != last_cmd:
        try:
            requests.get(f"http://{ESP_IP}/cmd?move={cmd}", timeout=0.1)
            last_cmd = cmd
        except:
            pass

    cv2.imshow("Frame", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
