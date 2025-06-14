import requests  # Para enviar solicitudes HTTP a la Raspberry Pi
import time  # Para gestionar tiempos y retardos
import whisper  # Modelo de transcripción automática (OpenAI Whisper)
import sounddevice as sd  # Para grabar audio desde el micrófono
import numpy as np  # Para procesar señales de audio
import scipy.io.wavfile  # Para guardar el audio en formato WAV

# CONFIGURACIÓN
RASPBERRY_IP = "192.168.1.100"  # Dirección IP de la Raspberry Pi
CONTROL_URL = f"http://{RASPBERRY_IP}:5000/control"  # URL para enviar comandos de control
VOICE_STATUS_URL = f"http://{RASPBERRY_IP}:5000/voice_status"  # URL para saber si el modo de voz está activo
DELAY = 1.0  # Tiempo mínimo entre comandos (antispam)
last_sent = 0  # Último momento en que se envió un comando
ultimo = [None]  # Último comando enviado (como lista para uso global)

# Establece el estado de grabación (ON/OFF) en el servidor
def set_recording_status(status):
    try:
        requests.post(f"http://{RASPBERRY_IP}:5000/set_recording", data={"status": status})
    except Exception as e:
        print("Error actualizando estado de grabación:", e)

# Consulta si el modo de control por voz está activado
def modo_voz_activado():
    try:
        r = requests.get(VOICE_STATUS_URL, timeout=0.5)
        return r.text.strip() == "ON"
    except:
        return False  # Si hay error de conexión, se asume que no está activado

# Graba audio desde el micrófono por una duración determinada
def grabar_audio(duracion=3, fs=16000):
    print("Grabando...")
    audio = sd.rec(int(duracion * fs), samplerate=fs, channels=1)  # Graba audio mono a 16 kHz
    sd.wait()  # Espera a que finalice la grabación
    audio = np.int16(audio * 32767)  # Escala a enteros de 16 bits
    scipy.io.wavfile.write('comando.wav', fs, audio)  # Guarda el archivo como WAV

# Usa Whisper para transcribir el audio grabado a texto
def transcribir_audio():
    model = whisper.load_model("tiny")  # Carga el modelo más pequeño (más rápido)
    result = model.transcribe("comando.wav", language="es")  # Transcribe en español
    texto = result['text'].lower()  # Convierte el texto a minúsculas
    print("Texto detectado:", texto)
    return texto

# Traduce el texto reconocido a comandos conocidos
def texto_a_comandos(texto):
    comandos = []
    if "izquierda" in texto:
        comandos.append("left")
    if "derecha" in texto:
        comandos.append("right")
    if "centro" in texto or "centra" in texto:
        comandos.append("center")
    if "arriba" in texto:
        comandos.append("up")
    if "abajo" in texto:
        comandos.append("down")
    return comandos

# Envía un comando a la Raspberry Pi
def enviar_comando(comando):
    global last_sent
    if time.time() - last_sent < DELAY:
        return  # No enviar si no ha pasado suficiente tiempo

    # Si hay cambio de dirección, se envía un "stop_" del anterior
    if ultimo[0] in ["left", "right", "up", "down"] and comando != ultimo[0]:
        try:
            requests.post(CONTROL_URL, data={"dir": f"stop_{ultimo[0]}"})
            print(f"Enviado: stop_{ultimo[0]}")
            time.sleep(0.2)  # Pausa breve para evitar solapamiento
        except Exception as e:
            print("Error enviando stop:", e)

    try:
        # Envía el nuevo comando
        requests.post(CONTROL_URL, data={"dir": comando})
        print(f"Enviado a RPi: {comando}")
        last_sent = time.time()  # Actualiza el tiempo de envío
        # Solo guarda comandos de dirección como último
        if comando in ["left", "right", "up", "down"]:
            ultimo[0] = comando
        else:
            ultimo[0] = None
    except Exception as e:
        print("Error al enviar comando:", e)

# --- Bucle principal del programa ---
if __name__ == "__main__":
    while True:
        if not modo_voz_activado():  # Comprueba si el modo de voz está habilitado
            print("Modo voz desactivado. Esperando...")
            time.sleep(1)
            continue

        set_recording_status("ON")  # Señaliza que comienza la grabación
        grabar_audio()  # Captura audio del micrófono
        set_recording_status("OFF")  # Señaliza que terminó

        texto = transcribir_audio()  # Transcribe lo grabado a texto
        comandos = texto_a_comandos(texto)  # Traduce el texto a comandos
        for cmd in comandos:
            enviar_comando(cmd)  # Envía cada comando reconocido

        time.sleep(0.5)  # Espera corta antes de volver a empezar