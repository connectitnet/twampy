import binascii
import socket
import sys
import threading

import logging
logger = logging.getLogger(__name__)

class udpSession(threading.Thread):

    def __init__(self, addr="", port=20000, tos=0, ttl=64, do_not_fragment=False, ipversion=4):
        threading.Thread.__init__(self)
        if ipversion == 6:
            self.bind6(addr, port, tos, ttl)
        else:
            self.bind(addr, port, tos, ttl, do_not_fragment)
        self.running = True

    def bind(self, addr, port, tos, ttl, df):
        logger.debug(
            "bind(addr=%s, port=%d, tos=%d, ttl=%d)", addr, port, tos, ttl)
        self.socket = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos)
        self.socket.setsockopt(socket.SOL_IP,     socket.IP_TTL, ttl)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((addr, port))
        if df:
            if (sys.platform == "linux2"):
                self.socket.setsockopt(socket.SOL_IP, 10, 2)
            elif (sys.platform == "win32"):
                self.socket.setsockopt(socket.SOL_IP, 14, 1)
            elif (sys.platform == "darwin"):
                logger.error("do-not-fragment can not be set on darwin")
            else:
                logger.error("unsupported OS, ignore do-not-fragment option")
        else:
            if (sys.platform == "linux2"):
                self.socket.setsockopt(socket.SOL_IP, 10, 0)

    def bind6(self, addr, port, tos, ttl):
        logger.debug(
            "bind6(addr=%s, port=%d, tos=%d, ttl=%d)", addr, port, tos, ttl)
        self.socket = socket.socket(
            socket.AF_INET6, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_TCLASS, tos)
        self.socket.setsockopt(
            socket.IPPROTO_IPV6, socket.IPV6_UNICAST_HOPS, ttl)
        self.socket.setsockopt(socket.SOL_SOCKET,   socket.SO_REUSEADDR, 1)
        self.socket.bind((addr, port))
        logger.info("Wait to receive test packets on [%s]:%d", addr, port)

    def sendto(self, data, address):
        logger.debug("transmit: %s", binascii.hexlify(data))
        self.socket.sendto(data, address)

    def recvfrom(self):
        data, address = self.socket.recvfrom(9216)
        logger.debug("received: %s", binascii.hexlify(data))
        return data, address

    def stop(self, signum, frame):
        logger.info("SIGINT received: Stop TWL session reflector")
        # if self.running and self.socket.
        self.running = False
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()