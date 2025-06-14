import cv2  # Librería para visión por computadora
import mediapipe as mp  # Framework de Google para detección de manos (entre otros)
import requests  # Para hacer solicitudes HTTP (enviar comandos)
import time  # Para gestionar tiempos y retardos

# CONFIGURACIÓN INICIAL
RASPBERRY_IP = "192.168.1.100"  # Dirección IP de la Raspberry Pi (cámbiala si es necesario)
CONTROL_URL = f"http://{RASPBERRY_IP}:5000/control"  # URL a la que se enviarán comandos de control
STATUS_URL = f"http://{RASPBERRY_IP}:5000/hand_status"  # URL para saber si el modo gestos está activado
DELAY = 1.0  # Tiempo mínimo entre comandos (antispam)
last_sent = 0  # Timestamp del último comando enviado
ultimo = None  # Guarda la última dirección enviada (para enviar "stop" si cambia)

# Configuración de MediaPipe para detectar manos
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,  # True solo si analizas imágenes sueltas, False para vídeo en tiempo real
    max_num_hands=1,  # Solo se detecta una mano
    min_detection_confidence=0.6,  # Confianza mínima para detectar
    min_tracking_confidence=0.6  # Confianza mínima para hacer seguimiento entre frames
)
mp_draw = mp.solutions.drawing_utils  # Utilidades para dibujar landmarks

# Cuenta el número de dedos levantados a partir de landmarks detectados
def contar_dedos(hand_landmarks):
    dedos = 0
    # Pulgar (compara posición x entre dedo 4 y 3)
    if hand_landmarks.landmark[4].x < hand_landmarks.landmark[3].x:
        dedos += 1
    # Otros dedos (compara posición y entre punta y articulación media)
    for tip in [8, 12, 16, 20]:
        if hand_landmarks.landmark[tip].y < hand_landmarks.landmark[tip - 2].y:
            dedos += 1
    return dedos

# Envía un comando a la Raspberry Pi
def enviar_comando(direccion):
    global last_sent, ultimo

    # Si el nuevo comando es distinto al anterior, y el anterior era de movimiento, se envía comando de "stop"
    if direccion != ultimo and ultimo in ["left", "right", "up", "down"]:
        try:
            requests.post(CONTROL_URL, data={"dir": f"stop_{ultimo}"})
            print(f"Parando: {ultimo}")
        except Exception as e:
            print("Error al parar:", e)

    # Si no ha pasado suficiente tiempo desde el último envío, se omite
    if time.time() - last_sent < DELAY:
        return

    try:
        # Envía el nuevo comando
        requests.post(CONTROL_URL, data={"dir": direccion})
        print(f"Enviado: {direccion}")
        last_sent = time.time()  # Actualiza el tiempo del último envío

        # Guarda el último comando si era de movimiento
        ultimo = direccion if direccion in ["left", "right", "up", "down"] else None
    except Exception as e:
        print("Error al enviar:", e)

# Traduce número de dedos levantados a un comando específico
def gesto_a_comando(dedos):
    if dedos == 1:
        return "left"
    elif dedos == 2:
        return "right"
    elif dedos == 3:
        return "up"
    elif dedos == 4:
        return "down"
    elif dedos == 5:
        return "center"
    return None  # Si no se detecta gesto válido

# Consulta a la Raspberry si el modo gestos está activado
def modo_gestos_activado():
    try:
        r = requests.get(STATUS_URL, timeout=0.5)
        return r.text.strip() == "ON"
    except:
        return True  # Si hay error de conexión, se asume que está activado (fallback)

# MAIN LOOP: inicializa cámara y comienza procesamiento
cap = cv2.VideoCapture(4, cv2.CAP_DSHOW)  # Abre cámara en índice 4 con backend DirectShow (Windows)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # Configura resolución
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# Verifica si la cámara pudo abrirse
if not cap.isOpened():
    print("No se pudo abrir la cámara en el índice 4 con backend CAP_DSHOW")
    exit()

print("Modo gestos activado")

# Bucle principal
while True:
    if not modo_gestos_activado():
        enviar_comando("stop")  # Envia "stop" si el modo está desactivado
        print("Modo gestos desactivado.")
        time.sleep(1)
        continue

    ret, frame = cap.read()  # Captura un frame
    if not ret:
        continue  # Si falla la captura, pasa al siguiente frame

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # Convierte a RGB para MediaPipe
    results = hands.process(frame_rgb)  # Procesa la imagen para detectar manos

    if results.multi_hand_landmarks:
        for handLms in results.multi_hand_landmarks:
            dedos = contar_dedos(handLms)  # Cuenta dedos levantados
            print(f"Dedos detectados: {dedos}")  # Mensaje de depuración
            comando = gesto_a_comando(dedos)  # Traduce el gesto a comando
            if comando:
                enviar_comando(comando)  # Envía el comando si es válido

            # Si deseas dibujar los landmarks sobre el frame (opcional):
            # mp_draw.draw_landmarks(frame, handLms, mp_hands.HAND_CONNECTIONS)

    # Mostrar el frame en ventana (opcional)
    # cv2.imshow("Detección de Gestos", frame)
    # if cv2.waitKey(1) & 0xFF == ord('q'):
        # break  # Salir si se presiona 'q'

# Libera la cámara y destruye ventanas al salir
cap.release()
cv2.destroyAllWindows()