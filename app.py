
from flask import Flask, render_template, Response, request
import cv2
import RPi.GPIO as GPIO
import time
import os
import threading

app = Flask(__name__)

# Reset de estado
for fname in ["eye_mode.txt", "voice_mode.txt", "hand_mode.txt", "person_mode.txt"]:
    if os.path.exists(fname):
        with open(fname, "w") as f:
            f.write("OFF")

# ----------------configuracion de hardware-----------------------
servo_PAN_PIN = 17 #vertical
servo_TILT_PIN = 27 #horizontal
fan_PIN = 22 #Ventilador

GPIO.setmode(GPIO.BCM)
GPIO.setup(servo_PAN_PIN, GPIO.OUT)
GPIO.setup(servo_TILT_PIN, GPIO.OUT)

GPIO.setup(fan_PIN, GPIO.OUT)
GPIO.output(fan_PIN, GPIO.LOW)


# Inicializa los pwm para los servos
servo_pan = GPIO.PWM(servo_PAN_PIN, 50)
servo_tilt = GPIO.PWM(servo_TILT_PIN, 50)

servo_pan.start(6) #posicoines iniciales neutras
servo_tilt.start(8.5)
time.sleep(1) # permite que los servos se estabilicen
servo_pan.ChangeDutyCycle(0)
servo_tilt.ChangeDutyCycle(0)

# Posiciones iniciales
pos_pan = 6 #centro vertical
pos_tilt = 8.5 #centro horizontal
paso = 0.01
min_duty = 2
max_duty = 17
PWM_POR_PIXEL = 0.005

# ----------------captura de video-----------------------

moving_flags = {'up': False, 'down': False, 'left': False, 'right': False}

def gen_frames():
    cap = cv2.VideoCapture(0)
    while True:
        success, frame = cap.read()
        if not success:
            break
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    cap.release()

# -------------------------------funciones de movimiento-------------------------------

def mover_continuo(eje, direccion):
    global pos_pan, pos_tilt
    while moving_flags[direccion]:
        if eje == 'pan':
            if direccion == 'down' and pos_pan - paso >= min_duty:
                pos_pan -= paso
                servo_pan.ChangeDutyCycle(pos_pan)
            elif direccion == 'up' and pos_pan + paso <= max_duty:
                pos_pan += paso
                servo_pan.ChangeDutyCycle(pos_pan)
        elif eje == 'tilt':
            if direccion == 'left' and pos_tilt + paso <= max_duty:
                pos_tilt += paso
                servo_tilt.ChangeDutyCycle(pos_tilt)
            elif direccion == 'right' and pos_tilt - paso >= min_duty:
                pos_tilt -= paso
                servo_tilt.ChangeDutyCycle(pos_tilt)
        time.sleep(0.0005)
        
        if eje == 'pan':
            servo_pan.ChangeDutyCycle(0)
        else:
            servo_tilt.ChangeDutyCycle(0)

def centrar():
    global pos_pan, pos_tilt
    pos_pan = 6
    pos_tilt = 8.5
    servo_pan.ChangeDutyCycle(pos_pan)
    servo_tilt.ChangeDutyCycle(pos_tilt)
    time.sleep(0.3)
    servo_pan.ChangeDutyCycle(0)
    servo_tilt.ChangeDutyCycle(0)

def mover_hacia_tilt_suave(target_cx):
    global pos_tilt
    FRAME_WIDTH = 640
    CENTER_X = FRAME_WIDTH // 2
    offset_x = target_cx - CENTER_X

    if abs(offset_x) < 5:
        return
    
    k = 0.0008
    step = min(max(abs(offset_x) * k, 0.01), 0.08)

    if offset_x > 0 and pos_tilt - step >= min_duty:
        pos_tilt -= step
    elif offset_x < 0 and pos_tilt + step <= max_duty:
        pos_tilt += step

    servo_tilt.ChangeDutyCycle(pos_tilt)
    time.sleep(0.05)
    servo_tilt.ChangeDutyCycle(0)
        
# --------------------------------interfaz web-------------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/eye_status')
def eye_status():
    if os.path.exists("eye_mode.txt"):
        with open("eye_mode.txt", "r") as f:
            return f.read().strip()
    return "OFF"

@app.route('/voice_status')
def voice_status():
    if os.path.exists("voice_mode.txt"):
        with open("voice_mode.txt", "r") as f:
            return f.read().strip()
    return "OFF"

@app.route('/hand_status')
def hand_status():
    if os.path.exists("hand_mode.txt"):
        with open("hand_mode.txt", "r") as f:
            return f.read().strip()
    return "OFF"

@app.route('/person_status')
def person_status():
    if os.path.exists("person_mode.txt"):
        with open("person_mode.txt","r") as f:
            return f.read().strip()
    return "OFF"

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/coords', methods=['POST'])
def coords():
    global pos_tilt

    data = request.get_json()
    if not data or 'x' not in data:
        return "Invalid data", 400

    cx = int(data['x'])

    mover_hacia_tilt_suave(cx)

    return "OK", 200

is_recording = False
@app.route('/recording_status')
def recording_status():
    return "ON" if is_recording else "OFF"

@app.route('/set_recording', methods=['POST'])
def set_recording():
    global is_recording
    estado = request.form['status']
    is_recording = (estado == "ON")
    return '', 204

@app.route('/control', methods=['POST'])
def control():
    direction = request.form['dir']
    if direction in moving_flags:
        moving_flags[direction] = True
        eje = 'pan' if direction in ['up', 'down'] else 'tilt'
        threading.Thread(target=mover_continuo, args=(eje, direction)).start()
    elif direction.startswith('stop_'):
        key = direction.replace('stop_', '')
        moving_flags[key] = False
    elif direction == 'center':
        centrar()
    elif direction == 'eyeon':
        with open("/home/lorenapablos4/Desktop/eye_mode.txt", "w") as f:
            f.write("ON")
            print("eye tracking activado")
    elif direction == 'eyeoff':
        with open("eye_mode.txt", "w") as f:
            f.write("OFF")
            print("Eyetracking parado")
    elif direction == 'voiceon':
        with open("/home/lorenapablos4/Desktop/voice_mode.txt", "w") as f:
            f.write("ON")
            print("Modo de voz activado")
    elif direction == 'voiceoff':
        with open("voice_mode.txt", "w") as f:
            f.write("OFF")
            print("Modo voz parado")
    elif direction == 'handon':
        with open("hand_mode.txt", "w") as f:
            f.write("ON")
            print("Modo hand activado")
    elif direction == 'handoff':
        with open("hand_mode.txt", "w") as f:
            f.write("OFF")
            print("Modo hand parado")
    elif direction == 'personon':
        with open("person_mode.txt", "w") as f:
            f.write("ON")
            print("Modo person activado")
    elif direction == 'personoff':
        with open("person_mode.txt", "w") as f:
            f.write("OFF")
            print("Modo person parado")
    elif direction == 'fanon':
        GPIO.output(fan_PIN, GPIO.HIGH)
        print("ventilador activo")
    elif direction == 'fanoff':
        GPIO.output(fan_PIN, GPIO.LOW)
        print("ventilador desactivado")
    elif direction == 'stop':
        for key in moving_flags:
            moving_flags[key] = False
        
        return "<h3>Sistema detenido correctamente. Puedes cerrar esta pagina.</h3>"
    
    return ('', 204) #indica que la solicitud fue completada

@app.route('/set_position', methods=['POST'])
def set_position():
    global  pos_tilt
    try:
        tilt_original = float(request.form['tilt'])
        #pos_pan = max(min(float(request.form['pan']), max_duty), min_duty)
        pos_tilt = max_duty - (tilt_original - min_duty)
        pos_tilt = max(min(pos_tilt, max_duty), min_duty)
           
        #servo_pan.ChangeDutyCycle(pos_pan)
        servo_tilt.ChangeDutyCycle(pos_tilt)
        time.sleep(0.05)
        #servo_pan.ChangeDutyCycle(0)
        servo_tilt.ChangeDutyCycle(0)
        
        
        return "OK", 200
    except Exception as e:
        return f"Error: {e}", 400



# -----------------limpieza segura---------------------------

def cleanup():
    servo_pan.stop()
    servo_tilt.stop()
    GPIO.cleanup()
    print("Recursos liberados correctamente.")
    
    
# -----------------ejecución------------------------------

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000)
    finally:
        cleanup()
                                                                                    