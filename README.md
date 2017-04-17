# neoudp
Put NeoPixels on your LAN.

Simple Arduino program to copy bits from UDP packets to an attached
string of NeoPixels. The basic concept is to make the Arduino simple
as possible and place all the complexity in a program somewhere else
on your network.

The UDP payload should be the bytes 0x27 0x1d 0x0a 0x3c followed by 4
bytes of *pixel data*, RGBW, for every NeoPixel in your string (send 4
bytes / pixel, even if the NeoPixels are only RGB).

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
and NeoPixel string.

Example `parameters.h` file: 
~~~~
#define STRIP_PIN  6
#define STRIP_LEN  32
#define UNIT_ID    03
#define PIXEL_TYPE NEO_GRB + NEO_KHZ800

#define SSID "Enterprise"
#define WIFI_PASSWORD "IAMADOCTORNOTANITGUY"
~~~~

## Power Limit Feature

While we want make the code running on the Arduino 'dumb', having it
protect itself against bugs in the remote program that might damage
the hardware is a good idea.

Some NeoPixel setups have limits on how much power they can safely can
draw. For example a NeoPixel feather wing should only draw 1A
sustained, and in practice the power supply of most feathers won't
actually support that high a current.

Empirically the current draw of a NeoPixels is linear in the sum of
the 3 (or 4) bytes that it has been set too. Providing a value for
`POWER_LIMIT` in `parameters.h` will cause the system to limit the sum
of bytes sent to the NeoPixels to `POWER_LIMIT`. If the sum of the
byte values in a packet's pixel data is greater than `POWER_LIMIT`
then each value will be scaled down by sum divided `POWER_LIMIT`
before sending the bytes to the NeoPixels.
