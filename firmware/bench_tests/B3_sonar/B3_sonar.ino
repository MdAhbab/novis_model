/*
  NOVIS Part B3 - HC-SR04 x2 ultrasonic test (ESP32)
  Status as of last session: wired, running, readings NOT yet confirmed
  stable against a fixed target - see docs/hardware_log.md section 6 before
  trusting this as a pass. Both sensors are wired at once (ahead of the
  guide's "left first" order) - worth isolating them if trouble persists.

  DANGER: HC-SR04 ECHO outputs 5V. The ESP32 is 3.3V-only. ECHO must go
  through a 1k/2k voltage divider - never straight into a GPIO.

      HC-SR04 ECHO --[1k]--+--[2k]-- GND
                            |
                      to ESP32 ECHO pin      (midpoint = 5V * 2/3 = 3.33V)

  Wiring (avoids the MLX90640's I2C on GPIO21/22):
  LEFT  TRIG -> GPIO16 (direct, no divider)   LEFT  ECHO -> divider -> GPIO17
  RIGHT TRIG -> GPIO18 (direct, no divider)   RIGHT ECHO -> divider -> GPIO19
  VCC on both -> 5V/VIN (USB power for the bench test)

  Status: PASS on hardware.

  PASS = distance readings that track a hand moving toward/away from the
  sensor, matching a ruler within a few mm at 30 cm. Always judge against a
  FIXED target - with nothing in front of the sensors, readings jump by
  metres from ambient reflections, and that is normal, not a fault.
*/

#define TRIG_LEFT   16
#define ECHO_LEFT   17
#define TRIG_RIGHT  18
#define ECHO_RIGHT  19

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);

  pinMode(TRIG_LEFT, OUTPUT);
  pinMode(ECHO_LEFT, INPUT);
  pinMode(TRIG_RIGHT, OUTPUT);
  pinMode(ECHO_RIGHT, INPUT);

  Serial.println("HC-SR04 test starting...");
}

// Returns distance in millimetres, or 0 if nothing was detected.
uint16_t readRange(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);       // datasheet asks for a 10 us pulse
  digitalWrite(trigPin, LOW);

  unsigned long duration = pulseIn(echoPin, HIGH, 30000UL);  // 30ms timeout, ~5m
  if (duration == 0) return 0;

  return (uint16_t)((duration * 343UL) / 2000UL);  // mm, round trip
}

void loop() {
  uint16_t left = readRange(TRIG_LEFT, ECHO_LEFT);
  delay(60);   // gap so the two sensors don't hear each other's pings (cross-talk)
  uint16_t right = readRange(TRIG_RIGHT, ECHO_RIGHT);

  Serial.print("Left: ");  Serial.print(left);  Serial.print(" mm   ");
  Serial.print("Right: "); Serial.print(right); Serial.println(" mm");

  delay(200);
}
