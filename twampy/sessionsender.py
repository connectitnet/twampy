import select
import struct
import random


from twampy.session import udpSession
from twampy.statistics import twampStatistics
from twampy.utils import parse_addr, now, time_ntp2py, generate_zero_bytes
from twampy.constants import TIMEOFFSET, ALLBITS


import logging
logger = logging.getLogger("twampy")


class SessionSender(udpSession):

    def __init__(self, near_end, far_end, count, interval, tos, ttl, padding, do_not_fragment):
        # Session Sender / Session Reflector:
        #   get Address, UDP port, IP version from near_end/far_end attributes
        sip, spt, sipv = parse_addr(near_end, 20000)
        rip, rpt, ripv = parse_addr(far_end,  20001)

        ipversion = 6 if (sipv == 6) or (ripv == 6) else 4
        udpSession.__init__(self, sip, spt, tos, ttl, do_not_fragment, ipversion)

        self.remote_addr = rip
        self.remote_port = rpt
        self.interval = float(interval) / 1000
        self.count = count
        self.stats = twampStatistics()

        if padding != -1:
            self.padmix = [padding]
        elif ipversion == 6:
            self.padmix = [0, 0, 0, 0, 0, 0, 0, 514, 514, 514, 514, 1438]
        else:
            self.padmix = [8, 8, 8, 8, 8, 8, 8, 534, 534, 534, 534, 1458]

    def run(self):
        schedule = now()
        endtime = schedule + self.count * self.interval + 5

        idx = 0
        while self.running:
            while select.select([self.socket], [], [], 0)[0]:
                t4 = now()
                data, address = self.recvfrom()

                if len(data) < 36:
                    logger.error("short packet received: %d bytes", len(data))
                    continue

                t3 = time_ntp2py(data[4:12])
                t2 = time_ntp2py(data[16:24])
                t1 = time_ntp2py(data[28:36])

                delayRT = max(0, 1000 * (t4 - t1 + t2 - t3))  # round-trip delay
                delayOB = max(0, 1000 * (t2 - t1))            # out-bound delay
                delayIB = max(0, 1000 * (t4 - t3))            # in-bound delay

                rseq = struct.unpack('!I', data[0:4])[0]
                sseq = struct.unpack('!I', data[24:28])[0]

                logger.info("Reply from %s [rseq=%d sseq=%d rtt=%.2fms outbound=%.2fms inbound=%.2fms]", address[0], rseq, sseq, delayRT, delayOB, delayIB)
                self.stats.add(delayRT, delayOB, delayIB, rseq, sseq)

                if sseq + 1 == self.count:
                    logger.info("All packets received back")
                    self.running = False

            t1 = now()
            if (t1 >= schedule) and (idx < self.count):
                schedule = schedule + self.interval

                data = struct.pack('!L2IH', idx, int(TIMEOFFSET + t1), int((t1 - int(t1)) * ALLBITS), 0x3fff)
                pbytes = generate_zero_bytes(self.padmix[int(len(self.padmix) * random.random())])

                self.sendto(data + pbytes, (self.remote_addr, self.remote_port))
                logger.info("Sent to %s [sseq=%d]", self.remote_addr, idx)

                idx = idx + 1
                if schedule > t1:
                    # TODO: Do something with r, w, e
                    r, w, e = select.select([self.socket], [], [], schedule - t1)

            if (t1 > endtime):
                logger.info("Receive timeout for last packet (don't wait anymore)")
                self.running = False

        self.stats.dump(idx)