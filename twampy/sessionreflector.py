import struct
import random


from twampy.session import udpSession
from twampy.utils import parse_addr, now, time_ntp2py, generate_zero_bytes
from twampy.constants import TIMEOFFSET, ALLBITS


import logging
logger = logging.getLogger("twampy")


class SessionReflector(udpSession):

    def __init__(self, near_end):
        addr, port, ipversion = parse_addr(near_end, 20001)

        # if padding != -1:
        #     self.padmix = [padding]
        # elif ipversion == 6:
        #     self.padmix = [0, 0, 0, 0, 0, 0, 0, 514, 514, 514, 514, 1438]
        # else:
        #     self.padmix = [8, 8, 8, 8, 8, 8, 8, 534, 534, 534, 534, 1458]

        udpSession.__init__(self, addr, port, ipversion)

    def run(self):
        index = {}
        reset = {}
        pbytes = {}

        while self.running:
            try:
                data, address = self.recvfrom()
                data_len = len(data)

                t2 = now()
                sec = int(TIMEOFFSET + t2)             # seconds since 1-JAN-1900
                msec = int((t2 - int(t2)) * ALLBITS)  # 32bit fraction of the second

                sseq = struct.unpack('!I', data[0:4])[0]
                t1 = time_ntp2py(data[4:12])

                logger.info("Request from %s:%d [sseq=%d outbound=%.2fms len=%dbytes]", address[0], address[1], sseq, 1000 * (t2 - t1), data_len)

                idx = 0
                if address not in index.keys():
                    logger.info("set rseq:=0     (new remote address/port)")
                    pbytes[address]=b''
                elif reset[address] < t2:
                    logger.info("reset rseq:=0   (session timeout, 30sec)")
                elif sseq == 0:
                    logger.info("reset rseq:=0   (received sseq==0)")
                    pbytes[address]=b''
                else:
                    idx = index[address]

                rdata = struct.pack('!L2I2H2I', idx, sec, msec, 0x001, 0, sec, msec)
                if not pbytes[address] and data_len > len(rdata):
                    padding = int(data_len-len(rdata)-14)
                    logger.debug('padding: %d zero bytes' % padding )
                    pbytes[address] = generate_zero_bytes(padding)
                self.sendto(rdata + data[0:14] + pbytes[address], address)

                index[address] = idx + 1
                reset[address] = t2 + 30  # timeout is 30sec

            except Exception as e:
                raise
                logger.debug('Exception: %s', str(e))
                break

        logger.info("TWL session reflector stopped")