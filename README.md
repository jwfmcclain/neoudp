# neoudp
Put Neopixels on your LAN.

Simple Arduino program to copy bits from UDP packets to an attached
string of neopixels. The basic concept is to make the Arduino simple
as possible and place all the complexity in a program somewhere else
on your network.

The UDP payload should be the bytes 0x27 0x1d 0x0a 0x3c followed by 4
bytes, RGBW, for every neopixel in your string (send 4 bytes / pixel,
even if the neopixels are only RGB).

If the Arduino receives a packet (including broadcast packets) with
the wrong length (something besides 4 + 4 * STRIP_LEN) it will send a
description packet back to the sender. The description packet payload
will be:

  * 4 byte magic : 0x27 0x1d 0x0a 0x3c
  * 1 byte 'unit id' : Set by `UNIT_ID`
  * 2 byte (big endian) string length : Set by `STRIP_LEN`
  * 1 byte channel count, 3 or 4 : Inferred from `PIXEL_TYPE`

The (single) `.ino` file assumes the there is a `parameters.h` file in
the same directory that provides information about your environment
and neopixel string.

Example `parameters.h` file: 
~~~~
#define STRIP_PIN  6
#define STRIP_LEN  32
#define UNIT_ID    03
#define PIXEL_TYPE NEO_GRB + NEO_KHZ800

#define SSID "Enterprise"
#define WIFI_PASSWORD "IAMADOCTORNOTANITGUY"
~~~~