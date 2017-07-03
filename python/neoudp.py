import socket
import sys
import time
import struct
import math
import threading
import Queue
import errno

from contextlib import contextmanager

def set_magic(buffer):
    buffer[0] = 0x27
    buffer[1] = 0x1d
    buffer[2] = 0x0a
    buffer[3] = 0x3c

discover_packet = bytearray(4)
set_magic(discover_packet)

server_port = 10000

#####################################################################
#
# Setup a single socket and thread for handling discovery.
#
# Client register handlers that get called whenever a neoudp packet is
# received. This is inline with the with recvfrom from call so these
# handlers shouldn't block.
#
# Handler gets the src address of the packet and the packet itself.
#
class DiscoveryListener:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        bind_addr = ('', 0)
        self.sock.bind(bind_addr)
        self.handlers = set()
        self.lock = threading.Lock()

    def add(self, handler):
        with self.lock:
            self.handlers.add(handler)

    def remove(self, handler):
        with self.lock:
            self.handlers.remove(handler)

    def send_discovery(self):
        self.sock.sendto(discover_packet, ('<broadcast>', server_port))

    @contextmanager
    def handler(self, handler_fn):
        self.add(handler_fn)
        yield
        self.remove(handler_fn)

    def run(self):
        while True:
            data, address = self.sock.recvfrom(4096)

            with self.lock:
                iset = frozenset(self.handlers)

            for handler in iset:
                handler(data, address)

listener = DiscoveryListener()
listener_thread = threading.Thread(target=listener.run, name="neoudp listener thread")
listener_thread.daemon = True
listener_thread.start()

def discover(unit_id=None, retry_fn=None):
    """Discover a neoudp server on the local network.

       Specify a unit_id if looking for a specific unit. If provided
       the thunk retry_fn will be called every time a new discovery
       packet is sent (after the first one).

       Blocks until it find a server, returns a Strip object.

    """

    packets = Queue.Queue()
    with listener.handler(lambda data, address: packets.put((data, address))):
        listener.send_discovery()

        while True:
            try:
                data, address = packets.get(True, 1)
            except Queue.Empty:
                # No response, try another query
                if retry_fn:
                    retry_fn()
                listener.send_discovery()
                continue

            if len(data) != 8:
                continue

            if data[:4] != discover_packet:
                continue

            found_unit_id, strip_length, channels = struct.unpack("!BHB", data[4:8])
            if unit_id and unit_id != found_unit_id:
                continue

            usock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            usock.connect(address)

            return Strip(strip_length, channels, found_unit_id, usock)

def print_dot():
    """Write and flush a '.' to stdout."""

    sys.stdout.write(".")
    sys.stdout.flush()

def console_driver(fn):
    unit_id = int(sys.argv[1])

    sys.stdout.write("Searching for unit %d:" % unit_id)
    sys.stdout.flush()

    strip = discover(unit_id, print_dot)

    sys.stdout.write("found %s\n" % strip)
    sys.stdout.flush()

    while True:
        try:
            fn(strip)
            return
        except socket.error as e:
            strip.close()

            if e.errno in (errno.EHOSTUNREACH, errno.EHOSTDOWN, errno.ENETUNREACH):
                sys.stdout.write("%s: %s disappeared: searching" % (time.strftime("%c"), strip))
                sys.stdout.flush()

                strip = discover(unit_id, print_dot)

                sys.stdout.write("found %s\n" % strip)
                sys.stdout.flush()
            else:
                raise

class Strip:
    """Client for a neoudp server.

       Use setPixelColor to set the color of a given NeoPixel. Call
       show to send the pixel data to the server. Color values are
       persistent between show calls, so if you set pixel 0 to a
       particular color, call show, set the color of other pixels and
       call show again, pixel 0 will keep its color.

    """

    def __init__(self, length, channels, unit_id, sock):
        self.id = unit_id
        self.channels = channels
        self.buffer = bytearray(4 + length * 4)
        set_magic(self.buffer)
        self.sock = sock

    def __len__(self):
        return ((len(self.buffer) - 4) / 4)

    def __str__(self):
        peer = self.sock.getpeername()
        return "neoudp.Strip unit id:%d at:%s:%d len:%d channels:%d" % (
            self.id, peer[0], peer[1], len(self), self.channels)

    def setPixelColor(self, i, r, g, b, w=0):
        """Set the color of NeoPixel 'i'.

           If the strip is a 3 color strip and w is non-zero then then
           r, g, b arguments will be ignored and the red, green, blue
           channels will each be set to w / 3.
        """
        offset = 4 + (i * 4)
        self.buffer[offset]     = r
        self.buffer[offset + 1] = g
        self.buffer[offset + 2] = b
        if self.channels == 3 and w > 0:
            self.buffer[offset]     = w/3
            self.buffer[offset + 1] = w/3
            self.buffer[offset + 2] = w/3
        elif self.channels == 4 and w > 0:
            self.buffer[offset + 3] = w


    def enumerate(self, start=0, step=1):
        return xrange(start, len(self), step)

    def offenum(self, start):
        """Enumerate each NeoPixels in the strip once starting at 'start' and wrapping and end of the strip."""
        start = start % len(self)
        for i in self.enumerate(start):
            yield i

        for i in xrange(0, start):
            yield i

    def clear(self):
        """Set all the pixels to off."""

        for i in self.enumerate():
            self.setPixelColor(i, 0, 0, 0)

    def show(self):
        """Send the current color data to the server.

           May throw an exception socket.send() throws."""
        self.sock.send(self.buffer)

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

    def close(self):
        self.sock.close()

class TriangleImpulse:
    """One shot triangle impulse."""

    def __init__(self, t0, height, duration):
        """Create a new impulse starting at 't0', lasting for 'duration' second, and value 'height'."""

        self.t0 = t0
        self.height = float(height)
        self.duration = float(duration)

    def eval_at(self, now):
        """Value of the function at time 'now'."""

        offset = now - self.t0
        if offset < 0:
            return 0

        if offset > self.duration:
            return 0

        half_duration = self.duration / 2
        halfset = math.fabs(offset - half_duration)
        return self.height * (1 - (halfset / half_duration))

    def is_done(self, now):
        """True iff eval_at will return 0 for all values > 'now'."""

        return now > self.duration + self.t0


def scale(v, f):
    """Scale v by f with clipping.

       Always returns an int between 0 and 255 inclusive."""

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
