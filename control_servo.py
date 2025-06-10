import RPi.GPIO as GPIO #permite controlar los pines GPIO de la Raspberry Pi
import time #se usa para introducir pausas (sleep) entre movimientos del servo

servoPIN = 17 # para comprobar el servo horizontal se pone 17 y para comprobar el servo vertical que pone 27
GPIO.setmode(GPIO.BCM) #Se establece el modo de numeración de pines: BCM (usa el número del pin GPIO, no el número físico de la placa)
GPIO.setup(servoPIN, GPIO.OUT) #Configura el pin como salida, ya que enviará señales al servo

p = GPIO.PWM(servoPIN, 50) # GPIO PWM con 50Hz
p.start(2.5) # Initialization
print("Starting servo!")
try:
  while True:
    p.ChangeDutyCycle(5) # Cambia la posición del servo a un nuevo ángulo (aproximadamente 45°) 
    time.sleep(0.5) #espera 0.5 segundos
    p.ChangeDutyCycle(7.5) # Cambia la posición del servo a un nuevo ángulo (aproximadamente 90°)
    time.sleep(0.5)
    p.ChangeDutyCycle(10) # Cambia la posición del servo a un nuevo ángulo (aproximadamente 135°)
    time.sleep(0.5)
    p.ChangeDutyCycle(12.5) # Cambia la posición del servo a un nuevo ángulo (aproximadamente 180°)
    time.sleep(0.5)
    p.ChangeDutyCycle(10)
    time.sleep(0.5)
    p.ChangeDutyCycle(7.5)
    time.sleep(0.5)
    p.ChangeDutyCycle(5)
    time.sleep(0.5)
    p.ChangeDutyCycle(2.5)
    time.sleep(0.5)
except KeyboardInterrupt:
  p.stop() #se detiene el PWM
  GPIO.cleanup() # se libera el control de los pines para evitar bloqueos o errores
