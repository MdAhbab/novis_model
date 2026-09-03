/*
  NOVIS Part B2 - MLX90640 thermal sensor test (ESP32) - PASS, confirmed on
  real hardware. Full 32x24 grid at 8 Hz, room ~27 C, hand in frame ~33-37 C.

  Wiring:
  ESP32 GPIO21 -> MLX90640 SDA      (4.7k pull-up to 3V3)
  ESP32 GPIO22 -> MLX90640 SCL      (4.7k pull-up to 3V3)
  ESP32 3V3    -> MLX90640 VIN
  ESP32 GND    -> MLX90640 GND
  ESP32 GND    -> MLX90640 PS       <-- required, see below

  Our module is a GY-MCU90640, not a plain MLX90640 breakout - it carries its
  own onboard STM32 that is the I2C master by default and fights us for the
  bus. PS tied to GND puts it into I2C passthrough mode. PS is only sampled at
  power-up, so you must fully unplug/replug USB after wiring it - a reset or
  EN press is not enough. Full investigation: docs/hardware_log.md section 4.

  PASS = a grid of numbers around room temperature (20-30), and holding a
  hand in front of the sensor pushes those pixels to about 30-35.
*/

#include <Wire.h>
#include <Adafruit_MLX90640.h>

Adafruit_MLX90640 mlx;
float frame[32 * 24];

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("Starting MLX90640 test...");

  Wire.begin(21, 22);      // PS must already be tied to GND (power-cycled after wiring)

  // 400 kHz is required to keep up with the 8 Hz refresh rate below: one frame
  // is 1664 bytes (~150 ms at 100 kHz, ~37 ms at 400 kHz) but a new frame
  // arrives every 125 ms. Too slow here and getFrame() returns -8 forever.
  Wire.setClock(400000);

  if (!mlx.begin(MLX90640_I2CADDR_DEFAULT, &Wire)) {
    Serial.println("ERROR: MLX90640 not found. Check wiring, and that PS is tied to GND.");
    while (1) delay(10);
  }
  Serial.println("MLX90640 found!");
  mlx.setMode(MLX90640_CHESS);
  mlx.setResolution(MLX90640_ADC_18BIT);
  mlx.setRefreshRate(MLX90640_8_HZ);
}

void loop() {
  int status = mlx.getFrame(frame);
  if (status == 0) {
    for (int y = 0; y < 24; y++) {
      for (int x = 0; x < 32; x++) {
        Serial.print(frame[y * 32 + x], 1);
        Serial.print(" ");
      }
      Serial.println();
    }
    Serial.println("-----");
  } else {
    Serial.print("getFrame failed, code: ");
    Serial.println(status);
  }
  delay(500);
}
