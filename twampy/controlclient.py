import binascii
import socket
import struct

from twampy.utils import generate_zero_bytes, now
from twampy.constants import TIMEOFFSET, TWAMP_PORT_DEFAULT, TOS_DEFAULT, TIMEOUT_DEFAULT

import logging
logger = logging.getLogger("twampy")


class ControlClient:

    
    def __init__(self, server, port=TWAMP_PORT_DEFAULT, timeout=TIMEOUT_DEFAULT, tos=TOS_DEFAULT, source_address=None):
        self.socket = socket.create_connection((server,tcp_port), timeout, source_address)
        pass

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self.socket.setsockopt(ip_protocol, socket.IP_TOS, tos)
        self.socket.connect((server, port))

    def send(self, data):
        logger.debug("CTRL.TX %s", binascii.hexlify(data))
        try:
            self.socket.send(data)
        except Exception as e:
            logger.critical('*** Sending data failed: %s', str(e))

    def receive(self):
        data = self.socket.recv(9216)
        logger.debug("CTRL.RX %s (%d bytes)", binascii.hexlify(data), len(data))
        return data

    def close(self):
        self.socket.close()

    def connectionSetup(self):
        logger.info("CTRL.RX <<Server Greeting>>")
        data = self.receive()
        self.smode = struct.unpack('!I', data[12:16])[0]
        logger.info("TWAMP modes supported: %d", self.smode)
        if self.smode & 1 == 0:
            logger.critical('*** TWAMPY only supports unauthenticated mode(1)')

        logger.info("CTRL.TX <<Setup Response>>")
        self.send(struct.pack('!I', 1) + generate_zero_bytes(160))

        logger.info("CTRL.RX <<Server Start>>")
        data = self.receive()

        rval = ord(data[15])
        if rval != 0:
            # TWAMP setup request not accepted by server
            logger.critical("*** ERROR CODE %d in <<Server Start>>", rval)

        self.nbrSessions = 0

    def reqSession(self, sender="", s_port=20001, receiver="", r_port=20002, startTime=0, timeOut=3, dscp=0, padding=0):
        typeP = dscp << 24

        if startTime != 0:
            startTime += now() + TIMEOFFSET

        if sender == "":
            request = struct.pack('!4B L L H H 13L 4ILQ4L', 5, 4, 0, 0, 0, 0, s_port, r_port, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, padding, startTime, 0, timeOut, 0, typeP, 0, 0, 0, 0, 0)
        elif sender == "::":
            request = struct.pack('!4B L L H H 13L 4ILQ4L', 5, 6, 0, 0, 0, 0, s_port, r_port, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, padding, startTime, 0, timeOut, 0, typeP, 0, 0, 0, 0, 0)
        elif ':' in sender:
            s = socket.inet_pton(socket.AF_INET6, sender)
            r = socket.inet_pton(socket.AF_INET6, receiver)
            request = struct.pack('!4B L L H H 16s 16s 4L L 4ILQ4L', 5, 6, 0, 0, 0, 0, s_port, r_port, s, r, 0, 0, 0, 0, padding, startTime, 0, timeOut, 0, typeP, 0, 0, 0, 0, 0)
        else:
            s = socket.inet_pton(socket.AF_INET, sender)
            r = socket.inet_pton(socket.AF_INET, receiver)
            request = struct.pack('!4B L L H H 16s 16s 4L L 4ILQ4L', 5, 4, 0, 0, 0, 0, s_port, r_port, s, r, 0, 0, 0, 0, padding, startTime, 0, timeOut, 0, typeP, 0, 0, 0, 0, 0)

        logger.info("CTRL.TX <<Request Session>>")
        self.send(request)
        logger.info("CTRL.RX <<Session Accept>>")
        data = self.receive()

        rval = ord(data[0])
        if rval != 0:
            logger.critical("ERROR CODE %d in <<Session Accept>>", rval)
            return False
        return True

    def startSessions(self):
        request = struct.pack('!B', 2) + generate_zero_bytes(31)
        logger.info("CTRL.TX <<Start Sessions>>")
        self.send(request)
        logger.info("CTRL.RX <<Start Accept>>")
        self.receive()

    def stopSessions(self):
        request = struct.pack('!BBHLQQQ', 3, 0, 0, self.nbrSessions, 0, 0, 0)
        logger.info("CTRL.TX <<Stop Sessions>>")
        self.send(request)

        self.nbrSessions = 0