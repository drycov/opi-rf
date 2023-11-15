import wiringpi as wp
import time
from collections import namedtuple

MAX_CHANGES = 67

Protocol = namedtuple('Protocol',
                      ['pulselength',
                       'sync_high', 'sync_low',
                       'zero_high', 'zero_low',
                       'one_high', 'one_low'])
PROTOCOLS = (None,
             Protocol(350, 1, 31, 1, 3, 3, 1),
             Protocol(650, 1, 10, 1, 2, 2, 1),
             Protocol(100, 30, 71, 4, 11, 9, 6),
             Protocol(380, 1, 6, 1, 3, 3, 1),
             Protocol(500, 6, 14, 1, 2, 2, 1),
             Protocol(200, 1, 10, 1, 5, 1, 1))

class RFDevice:
    def __init__(self, gpio,
                 tx_proto=1, tx_pulselength=None, tx_repeat=10, tx_length=24, rx_tolerance=80):
        self.gpio = gpio
        self.tx_enabled = False
        self.tx_proto = tx_proto
        if tx_pulselength:
            self.tx_pulselength = tx_pulselength
        else:
            self.tx_pulselength = PROTOCOLS[tx_proto].pulselength
        self.tx_repeat = tx_repeat
        self.tx_length = tx_length
        self.rx_enabled = False
        self.rx_tolerance = rx_tolerance
        self._rx_timings = [0] * (MAX_CHANGES + 1)
        self._rx_last_timestamp = 0
        self._rx_change_count = 0
        self._rx_repeat_count = 0
        self.rx_code = None
        self.rx_code_timestamp = None
        self.rx_proto = None
        self.rx_bitlength = None
        self.rx_pulselength = None
        wp.wiringPiSetup()

    def cleanup(self):
        if self.tx_enabled:
            self.disable_tx()
        if self.rx_enabled:
            self.disable_rx()
        wp.pinMode(self.gpio, 0)

    def enable_tx(self):
        if self.rx_enabled:
            return False
        if not self.tx_enabled:
            self.tx_enabled = True
            wp.pinMode(self.gpio, 1)
        return True

    def disable_tx(self):
        if self.tx_enabled:
            wp.pinMode(self.gpio, 0)
            self.tx_enabled = False
        return True

    def tx_code(self, code, tx_proto=None, tx_pulselength=None, tx_length=None):
        if tx_proto:
            self.tx_proto = tx_proto
        else:
            self.tx_proto = 1
        if tx_pulselength:
            self.tx_pulselength = tx_pulselength
        elif not self.tx_pulselength:
            self.tx_pulselength = PROTOCOLS[self.tx_proto].pulselength
        if tx_length:
            self.tx_length = tx_length
        elif self.tx_proto == 6:
            self.tx_length = 32
        elif (code > 16777216):
            self.tx_length = 32
        else:
            self.tx_length = 24
        rawcode = format(code, '#0{}b'.format(self.tx_length + 2))[2:]
        if self.tx_proto == 6:
            nexacode = ""
            for b in rawcode:
                if b == '0':
                    nexacode = nexacode + "01"
                if b == '1':
                    nexacode = nexacode + "10"
            rawcode = nexacode
            self.tx_length = 64
        return self.tx_bin(rawcode)

    def tx_bin(self, rawcode):
        for _ in range(0, self.tx_repeat):
            if self.tx_proto == 6:
                if not self.tx_sync():
                    return False
            for byte in range(0, self.tx_length):
                if rawcode[byte] == '0':
                    if not self.tx_l0():
                        return False
                else:
                    if not self.tx_l1():
                        return False
            if not self.tx_sync():
                return False
        return True

    def tx_l0(self):
        return self.tx_waveform(PROTOCOLS[self.tx_proto].zero_high,
                                PROTOCOLS[self.tx_proto].zero_low)

    def tx_l1(self):
        return self.tx_waveform(PROTOCOLS[self.tx_proto].one_high,
                                PROTOCOLS[self.tx_proto].one_low)

    def tx_sync(self):
        return self.tx_waveform(PROTOCOLS[self.tx_proto].sync_high,
                                PROTOCOLS[self.tx_proto].sync_low)

    def tx_waveform(self, highpulses, lowpulses):
        if not self.tx_enabled:
            return False
        wp.digitalWrite(self.gpio, 1)
        self._sleep((highpulses * self.tx_pulselength) / 1000000)
        wp.digitalWrite(self.gpio, 0)
        self._sleep((lowpulses * self.tx_pulselength) / 1000000)
