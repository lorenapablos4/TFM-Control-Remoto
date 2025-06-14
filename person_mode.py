import cv2  # Librería de visión por computadora
import time  # Para pausas entre frames
import requests  # Para enviar datos a la Raspberry Pi
from ultralytics import YOLO  # Importa modelo YOLO para detección de objetos

# CONFIGURACIÓN
RASPBERRY_IP = "192.168.1.100"  # Dirección IP de la Raspberry Pi
COORDS_URL = f"http://{RASPBERRY_IP}:5000/coords"  # URL para enviar coordenadas de la persona detectada
STATUS_URL = f"http://{RASPBERRY_IP}:5000/person_status"  # URL para verificar si el modo PERSON está activado
FRAME_SKIP = 5  # Número de frames a saltar entre detecciones (mejora rendimiento)

# CARGA DEL MODELO YOLOv8 (versión pequeña para eficiencia)
model = YOLO("yolov8n.pt")  # Usa el modelo preentrenado YOLOv8 nano

# CAPTURA DE VÍDEO desde el stream IP de la cámara
cap = cv2.VideoCapture("http://192.168.1.100:8080/?action=stream")
FRAME_WIDTH = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
FRAME_HEIGHT = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
CENTER_X = FRAME_WIDTH // 2  # Coordenada X del centro de la imagen
CENTER_Y = FRAME_HEIGHT // 2  # Coordenada Y del centro de la imagen

# CONFIGURACIÓN DE ZONAS EN PANTALLA
CENTER_BOX_WIDTH = 60  # Ancho de la caja verde central
CENTER_BOX_HEIGHT = 180  # Alto de la caja verde central
PERSON_BOX_SIZE = 30  # Tamaño del cuadrado azul sobre la persona

# Comprueba si el modo de seguimiento de persona está activado
def person_mode_on():
    try:
        r = requests.get(STATUS_URL, timeout=0.5)
        return r.text.strip() == "ON"
    except:
        return False  # Si hay error, se asume que no está activado

# Comprueba si la persona está dentro del área central (horizontalmente)
def dentro_de_caja_horizontal(cx, target_x, ancho):
    return target_x - ancho <= cx <= target_x + ancho

frame_count = 0  # Contador de frames para control de salto

while True:
    if not person_mode_on():
        print("Modo PERSON desactivado. Esperando...")
        time.sleep(1)
        continue  # Si no está activado, espera y vuelve a empezar

    ret, frame = cap.read()  # Captura un frame del stream
    if not ret:
        continue  # Si no se pudo leer el frame, intenta de nuevo

    frame_count += 1
    if frame_count % FRAME_SKIP != 0:
        # Dibuja caja verde de centrado aunque no se detecte persona (en frames intermedios)
        cv2.rectangle(frame,
                      (CENTER_X - CENTER_BOX_WIDTH, CENTER_Y - CENTER_BOX_HEIGHT),
                      (CENTER_X + CENTER_BOX_WIDTH, CENTER_Y + CENTER_BOX_HEIGHT),
                      (0, 255, 0), 2)
        cv2.imshow("Seguimiento", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break  # Salir si se presiona 'q'
        continue

    # Realiza detección de objetos usando YOLO en el frame actual
    results = model(frame, verbose=False)[0]
    # Filtra solo las detecciones de clase 0 (persona)
    personas = [b for b in results.boxes.data if int(b[5]) == 0]

    estado = "No detectado"
    if personas:
        # Selecciona la persona más centrada horizontalmente
        mejor = min(personas, key=lambda b: abs(((b[0] + b[2]) / 2) - CENTER_X))
        x1, y1, x2, y2, _, _ = mejor.tolist()
        cx = int((x1 + x2) / 2)  # Centro X del bounding box
        cy = int((y1 + y2) / 2)  # Centro Y del bounding box

        # Dibuja un punto rojo en el centro de la persona detectada
        cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)

        # Dibuja una caja azul sobre la persona
        cv2.rectangle(frame,
                      (cx - PERSON_BOX_SIZE, cy - PERSON_BOX_SIZE),
                      (cx + PERSON_BOX_SIZE, cy + PERSON_BOX_SIZE),
                      (255, 0, 0), 2)

        # Dibuja la caja verde de centrado
        cv2.rectangle(frame,
                      (CENTER_X - CENTER_BOX_WIDTH, CENTER_Y - CENTER_BOX_HEIGHT),
                      (CENTER_X + CENTER_BOX_WIDTH, CENTER_Y + CENTER_BOX_HEIGHT),
                      (0, 255, 0), 2)

        if not dentro_de_caja_horizontal(cx, CENTER_X, CENTER_BOX_WIDTH):
            print(f"[MOVER] Persona descentrada en X={cx}, centrando...")
            try:
                # Envía la coordenada X al servidor para que el servo corrija la posición
                requests.post(COORDS_URL, json={"x": cx})
            except Exception as e:
                print("Error al mover servo:", e)
        else:
            print(f"[OK] Persona centrada en X={cx}")
            estado = "Centrada"
    else:
        print("No se detectó persona.")  # Si no se detectó ninguna persona

    # Muestra el estado en pantalla
    cv2.putText(frame, estado, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.imshow("Seguimiento", frame)  # Muestra el frame con anotaciones
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break  # Sale del bucle si se presiona la tecla 'q'

# Libera los recursos
cap.release()
cv2.destroyAllWindows()