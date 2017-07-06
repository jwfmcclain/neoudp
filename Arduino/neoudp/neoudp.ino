#include <WiFi101.h>
#include <WiFiUdp.h>
#include <Adafruit_NeoPixel.h>
#include "parameters.h"

#define LEDPIN 13

char ssid[] = SSID;
char pass[] = WIFI_PASSWORD;
int status = WL_IDLE_STATUS;
IPAddress ip;

Adafruit_NeoPixel strip = Adafruit_NeoPixel(STRIP_LEN, STRIP_PIN, PIXEL_TYPE);

#define UDPSIZE 4 + 4 * STRIP_LEN

WiFiUDP Udp;
unsigned int localPort = 10000;
char packetBuffer[UDPSIZE];

#define ID_REPLY_LEN 8
char reply[ID_REPLY_LEN];

byte channel_count = 3;

void setup() {
  pinMode(LEDPIN, OUTPUT);

  // Don't wait forever if we aren't hooked up to a serial device.
  for (int i=0; i<5 && !Serial; i++) {
    delay(1000);
  }

  Serial.begin(9600);

  Serial.println("NEOUDP on WINC1500");

  WiFi.setPins(8,7,4,2);

  // Initialize the Client
  Serial.print(F("\nInit the WiFi module..."));
  // Check for the presence of the WiFi board / chip
  if (WiFi.status() == WL_NO_SHIELD) {
    Serial.println("WINC1500 not present");
    // don't continue:
    while (true);
  }

  String fv = WiFi.firmwareVersion();
  Serial.print("Firmware version installed: ");
  Serial.println(fv);

  try_wifi();
  Serial.println("ATWINC OK!");

  // Figure out number of channels, if bits 7 and 6 of the type byte
  // match bits 5 and 4 then it is a three color strip.
  //
  // https://github.com/adafruit/Adafruit_NeoPixel/blob/master/Adafruit_NeoPixel.h
  //
  byte strip_type   = 0xFF & PIXEL_TYPE;
  byte white_offset = (strip_type >> 6) & 0x03;
  byte red_offset   = (strip_type >> 4) & 0x03;
  if (white_offset != red_offset) {
    channel_count = 4;
  }

  unsigned short strip_length = STRIP_LEN;

  reply[0] = 0x27; // Magic
  reply[1] = 0x1d;
  reply[2] = 0x0a;
  reply[3] = 0x3c;
  reply[4] = UNIT_ID;  // ID
  reply[5] = 0xFF & (strip_length >> 8); // Length, high byte
  reply[6] = 0xFF & strip_length;        // Length, low byte
  reply[7] = channel_count;

  Serial.println("\nStarting server...");
  Udp.begin(localPort);

  // Test / indicate sucess
  strip.begin();
  strip.show(); // Initialize all pixels to 'off'

  colorWipe(strip.Color(255,   0,   0,   0), 100); // Red
  colorWipe(strip.Color(  0, 255,   0,   0), 100); // Green
  colorWipe(strip.Color(  0,   0, 255,   0), 100); // Blue
  if (channel_count == 3) {
    colorWipe(strip.Color(255, 255, 255, 0), 100); // White
  } else {
    colorWipe(strip.Color(0, 0, 0, 255), 100); // White
  }
  colorWipe(strip.Color(  0,   0,   0,   0), 100); // Off
}

void loop() {
  // If there's data available, read a packet
  //
  digitalWrite(LEDPIN, HIGH);
  int packetSize = Udp.parsePacket();
  digitalWrite(LEDPIN, LOW);

  if (packetSize) {

    Serial.print("Received packet of size ");
    Serial.println(packetSize);
    Serial.print("From ");
    IPAddress remoteIp = Udp.remoteIP();
    Serial.print(remoteIp);
    Serial.print(", port ");
    Serial.println(Udp.remotePort());

    // Read the packet into packetBufffer
    int len = Udp.read(packetBuffer, UDPSIZE);

    if (len < 4) {
      Serial.print("No magic, packet length: ");
      Serial.println(len);
      return;
    }

    if (packetBuffer[0] != 0x27 || packetBuffer[1] != 0x1d ||
	packetBuffer[2] != 0x0a || packetBuffer[3] != 0x3c)
    {
      Serial.println("Unexpected magic");
      return;
    }

    if (len != UDPSIZE) {
      // Wrong length, assume it is a discovery packet and send a
      // reply.
      //
      Serial.print("Unexpected packet length: ");
      Serial.println(len);

      Serial.print("Sending reply to: "); Serial.print(Udp.remoteIP()); Serial.print(" beginPacket:");
      Serial.println(Udp.beginPacket(Udp.remoteIP(), Udp.remotePort()));
      Serial.print("write: "); Serial.println(Udp.write(reply, ID_REPLY_LEN));
      Serial.print("endPacket: "); Serial.println(Udp.endPacket());

      return;
    }

    // Else push the bits out to the strip
    //

    char *led_data = &packetBuffer[4];
    int data_len = 4 * STRIP_LEN;

    // Is there a power limit set?
#ifdef POWER_LIMIT
    uint32_t sum = 0;

    for (int i=0; i<data_len; i++) {
      sum += led_data[i];
    }

    if (sum > POWER_LIMIT) {
      float scale = POWER_LIMIT / (float)sum;

      Serial.print("Sum: "); Serial.print(sum);
      Serial.print(" POWER_LIMIT: "); Serial.print(POWER_LIMIT);
      Serial.print(" Scaling by "); Serial.println(scale);

      for (int i=0; i<data_len; i++) {
	led_data[i] *= scale;
      }
    }
#endif

    for (int i=0; i<STRIP_LEN; i++) {
      int offset = i * 4;

      strip.setPixelColor(i,
			  led_data[offset],
			  led_data[offset+1],
			  led_data[offset+2],
			  led_data[offset+3]);
    }

    strip.show();
  }
}

// Fill the dots one after the other with a color
void colorWipe(uint32_t c, uint8_t wait) {
  for(uint16_t i=0; i<strip.numPixels(); i++) {
    strip.setPixelColor(i, c);
    strip.show();
    delay(wait);
  }
}


void wifi_check_delay() {
  digitalWrite(LEDPIN, LOW);
  delay(500);
  digitalWrite(LEDPIN, HIGH);
  delay(500);
}

void try_wifi() {
  do {
      Serial.print("Attempting to connect to SSID: ");
      Serial.println(ssid);
      // Connect to WPA/WPA2 network. Change this line if using open or WEP network:
      status = WiFi.begin(ssid, pass);

      // wait 10 seconds for connection:
      uint8_t timeout = 10;
      while (timeout > 0 && (WiFi.status() != WL_CONNECTED)) {
	Serial.print("WiFi Loop: WiFi.status() != WL_CONNECTED:");
	Serial.println(WiFi.status());
	timeout--;
	wifi_check_delay();
      }
  } while (WiFi.status() != WL_CONNECTED);

  int32_t rssi = WiFi.RSSI();
  Serial.print("WiFi.RSSI():");
  Serial.println(rssi);

  ip = WiFi.localIP();
  Serial.println(ip);
}
