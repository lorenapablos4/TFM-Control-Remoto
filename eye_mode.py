from pythonosc import dispatcher, osc_server # Importa módulos necesarios para recibir mensajes OSC
import threading # Para ejecutar el servidor OSC en un hilo separado
import requests # Para hacer peticiones HTTP a la Raspberry Pi
import time # Para pausas temporales

# Dirección IP de la Raspberry Pi y URLs para enviar y recibir datos
RASPBERRY_IP = "192.168.1.100"
SET_POSITION_URL = f"http://{RASPBERRY_IP}:5000/set_position"  # URL para enviar nuevas posiciones
STATUS_URL = f"http://{RASPBERRY_IP}:5000/eye_status" # URL para comprobar si el seguimiento ocular está activo

# Rango de valores del servo (duty cycle)
min_duty = 2
max_duty = 17

# Resolución de la pantalla para mapear coordenadas oculares
screen_width = 1920
screen_height = 1080

# Estado compartido del sistema: coordenadas de la mirada y última posición enviada
state = {
    "gaze": {"x": 960, "y": 540}, # Coordenadas iniciales al centro de la pantalla
    "last_tilt": 7.5, # Último valor enviado para tilt (horizontal)
    "last_pan": 6.0  # se mantiene fija la posición actual
}

# Función que consulta el estado del seguimiento ocular desde la Raspberry Pi
def eye_tracking_activado():
    try:
        r = requests.get(STATUS_URL, timeout=0.5) # Se hace una solicitud rápida para evitar bloqueo
        estado = r.text.strip()
        print("Estado desde /eye_status:", repr(estado)) # Muestra el estado recibido
        return estado == "ON" # Devuelve True si está activo
    except Exception as e:
        print("Error consultando eye_status:", e)
        return False

# Función para mapear un valor de un rango a otro (útil para traducir coordenadas a duty cycle)
def map_range(value, in_min, in_max, out_min, out_max):
    return max(out_min, min(out_max, (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min))

# Funciones manejadoras de eventos OSC para actualizar las coordenadas de la mirada
def on_gaze_x(unused_addr, args, value):
    state["gaze"]["x"] = value # Actualiza solo la coordenada X

def on_gaze_y(unused_addr, args, value):
    state["gaze"]["y"] = value  # se conserva aunque no lo usamos

# Bucle principal de procesamiento de las coordenadas de mirada
def procesamiento_loop():
    while True:
        if not eye_tracking_activado(): # Verifica si el seguimiento ocular está activo
            print("EyeTracking desactivado.")
            time.sleep(1)
            continue # Si no está activo, espera y vuelve a intentarlo

        x = state["gaze"]["x"] # Toma la coordenada X actual

        # Limitar bordes extremos para tilt
        usable_x = max(200, min(x, screen_width - 200))

        new_tilt = map_range(usable_x, 200, screen_width - 200, min_duty, max_duty)  # Mapea la coordenada X a un valor de tilt (duty cycle del servo)
        new_tilt = 0.6 * state["last_tilt"] + 0.4 * new_tilt  # suavizado
        
        # Solo actualiza si el cambio es significativo
        if abs(new_tilt - state["last_tilt"]) > 0.05:
            state["last_tilt"] = new_tilt
        else:
            new_tilt = state["last_tilt"]

        try:
            r = requests.post(SET_POSITION_URL, data={  # Envía el nuevo valor de tilt (pan se mantiene fijo)
                
                "pan": state["last_pan"],      # NO se modifica
                "tilt": new_tilt               # SOLO se ajusta el horizontal
            }, timeout=0.2)

            print(f"x={x:.1f} → tilt={new_tilt:.2f} (pan fijo: {state['last_pan']:.2f}) | {r.status_code}")

        except Exception as e:
            print("Error al enviar coordenadas:", e)

        time.sleep(0.1)

# Configuración del servidor OSC: mapeo de rutas a funciones
disp = dispatcher.Dispatcher()
disp.map("/gaze/x", on_gaze_x, "x")
disp.map("/gaze/y", on_gaze_y, "y")

# Inicialización del servidor OSC en localhost y puerto 57122
ip = "127.0.0.1"
port = 57122
server = osc_server.ThreadingOSCUDPServer((ip, port), disp)
print(f"Servidor OSC activo en {ip}:{port}")

# Inicia el servidor OSC en un hilo en segundo plano
threading.Thread(target=server.serve_forever, daemon=True).start()
# Comienza el bucle principal de procesamiento
procesamiento_loop()
