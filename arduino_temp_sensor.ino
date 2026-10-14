#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ArduinoJson.h>

// DS18B20 connected to GPIO 4
#define ONE_WIRE_BUS 4

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

// Set LCD I2C address (0x27 is standard, some modules use 0x3F)
LiquidCrystal_I2C lcd(0x27, 16, 2);

// Timing
unsigned long lastSerialSend = 0;
const unsigned long serialInterval = 2000; // Send every 2 seconds

void setup() {
  Serial.begin(115200);

  // Initialize LCD
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Tilapiers Feeder");
  lcd.setCursor(0, 1);
  lcd.print("Initializing...");

  // Initialize Temperature Sensor
  sensors.begin();
  delay(2000);
  lcd.clear();
}

void loop() {
  unsigned long currentMillis = millis();

  sensors.requestTemperatures();
  float tempC = sensors.getTempCByIndex(0);

  if (tempC == DEVICE_DISCONNECTED_C) {
    // Print to Serial as JSON (for dashboard integration)
    Serial.println("{\"status\":\"error\",\"message\":\"DS18B20 not detected\"}");

    // Print to LCD
    lcd.setCursor(0, 0);
    lcd.print("Temp: Sensor Err");
    lcd.setCursor(0, 1);
    lcd.print("Check Wiring    ");
  } else {
    float tempF = sensors.toFahrenheit(tempC);

    // Send JSON data to serial for dashboard integration
    if (currentMillis - lastSerialSend >= serialInterval) {
      StaticJsonDocument<128> doc;
      doc["status"] = "ok";
      doc["temperature_c"] = round(tempC * 10) / 10.0; // 1 decimal place
      doc["temperature_f"] = round(tempF * 10) / 10.0;
      doc["timestamp"] = currentMillis;
      doc["source"] = "arduino_ds18b20";

      serializeJson(doc, Serial);
      Serial.println(); // Newline to separate JSON objects

      lastSerialSend = currentMillis;
    }

    // Display on LCD Line 1: Celsius
    lcd.setCursor(0, 0);
    lcd.print("Temp: ");
    lcd.print(tempC, 1); // 1 decimal place
    lcd.print((char)223); // Degree symbol °
    lcd.print("C   ");

    // Display on LCD Line 2: Fahrenheit
    lcd.setCursor(0, 1);
    lcd.print("Temp: ");
    lcd.print(tempF, 1);
    lcd.print((char)223);
    lcd.print("F   ");
  }

  delay(500); // Refresh LCD every 500ms, but serial sends at 2s intervals
}
