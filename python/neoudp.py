import socket
import sys
import time
import struct
import math

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_address = ('192.168.1.33', 10000)

def set_magic(buffer):
    buffer[0] = 0x27 
    buffer[1] = 0x1d
    buffer[2] = 0x0a
    buffer[3] = 0x3c    

def discover(unit_id=None):
    buf = bytearray(4)
    set_magic(buf)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    bind_addr = ('', 10000)
    sock.bind(bind_addr)

    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    sock.sendto(buf, ('<broadcast>', 10000))

    while True:
        data, address = sock.recvfrom(4096)
        if len(data) != 8:
            continue
        
        if data[:4] != buf:
            continue

        found_unit_id, strip_length, channels = struct.unpack("!BHB", data[4:8])
        if unit_id and unit_id != found_unit_id:
            continue

        usock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        usock.connect(address)

        return Strip(strip_length, channels, found_unit_id, usock)
    

class Strip:
    def __init__(self, length, channels, unit_id, sock=None):
        self.id = unit_id
        self.channels = channels
        self.buffer = bytearray(4 + length * 4)
        set_magic(self.buffer)
        self.sock = sock

    def __len__(self):
        return ((len(self.buffer) - 4) / 4)

    def __str__(self):
        return "neoudp.Strip unit id:%d len:%d channels:%d" % (
            self.id, len(self), self.channels)
    
    def setPixelColor(self, i, r, g, b, w=0):
        offset = 4 + (i * 4)
        self.buffer[offset]     = r
        self.buffer[offset + 1] = g
        self.buffer[offset + 2] = b
        if self.channels == 3 and w > 0:
            self.buffer[offset]     = w/3
            self.buffer[offset + 1] = w/3
            self.buffer[offset + 2] = w/3
            

    def enumerate(self, start=0, step=1):
        return xrange(start, len(self), step)

    def offenum(self, start):
        start = start % len(self)
        for i in self.enumerate(start):
            yield i

        for i in xrange(0, start):
            yield i
    
    def show(self):
        if self.sock:
            self.sock.send(self.buffer)
        else:
            sock.sendto(self.buffer, server_address)

    def colorWipe(self, r, g, b, wait):
        for i in self.enumerate():
            self.setPixelColor(i, r, g, b)
            self.show();
            time.sleep(wait)

    def theaterChase(self, r, g, b, wait):
        for j in xrange(10):
            for q in xrange(3):
                for i in self.enumerate(q, 3):
                    self.setPixelColor(i, r, g, b)

                self.show()
                time.sleep(wait)

                for i in self.enumerate(q, 3):
                    self.setPixelColor(i, 0, 0, 0)

    def rainbow(self, wait):
        for j in xrange(256):
            for i in self.enumerate():
                self.setPixelColor(i, *wheel((i+j) % 256))

            self.show()
            time.sleep(wait)

    def rainbowCycle(self, wait):
        for j in xrange(256*5):
            for i in self.enumerate():
                self.setPixelColor(i, *wheel(((i * 256 / len(self) + j) % 255)))

            self.show()
            time.sleep(wait)

    def theaterChaseRainbow(self, wait):
        for j in xrange(256):
            for q in xrange(3):
                for i in self.enumerate(q, 3):
                    self.setPixelColor(i, *wheel((i-q+j) % 255))

                self.show()
                time.sleep(wait)

                for i in self.enumerate(q, 3):
                    self.setPixelColor(i, 0, 0, 0)

class TriangleImpulse:
    def __init__(self, t0, height, duration):
        self.t0 = t0
        self.height = float(height)
        self.duration = float(duration)
        
    def eval_at(self, now):
        offset = now - self.t0
        if offset < 0:
            return 0

        if offset > self.duration:
            return 0

        half_duration = self.duration / 2
        halfset = math.fabs(offset - half_duration)
        return self.height * (1 - (halfset / half_duration))

    def is_done(self, now):
        return now > self.duration + self.t0

        
def scale(v, f):
    r = int(round(v*f))
    if r < 0:
        return 0
    if r > 255:
        return 255
    return r

def wheel(p):
    p = 255 - p
    if p < 85:
        return (255 - p * 3, 0, p * 3)

    if p < 170:
        p -= 85
        return (0, p * 3, 255-p*3)

    p -= 170
    return (p * 3, 255-p*3, 0)
