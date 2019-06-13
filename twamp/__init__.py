#!/usr/bin/python

##############################################################################
#                                                                            #
#  Objective:                                                                #
#    Python implementation of the Two-Way Active Measurement Protocol        #
#    (TWAMP and TWAMP light) as defined in RFC5357.                          #
#                                                                            #
#  Features supported:                                                       #
#    - unauthenticated mode                                                  #
#    - IPv4 and IPv6                                                         #
#    - Support for DSCP, Padding, JumboFrames, IMIX                          #
#    - Support to set DF flag (don't fragment)                               #
#    - Basic Delay, Jitter, Loss statistics (jitter according to RFC1889)    #
#                                                                            #
#  Modes of operation:                                                       #
#    - TWAMP Controller                                                      #
#        combined Control Client, Session Sender                             #
#    - TWAMP Control Client                                                  #
#        to run TWAMP light test session sender against TWAMP server         #
#    - TWAMP Test Session Sender                                             #
#        same as TWAMP light                                                 #
#    - TWAMP light Reflector                                                 #
#        same as TWAMP light                                                 #
#                                                                            #
#  Limitations:                                                              #
#    As there is no hardware based timestamping, latency and jitter values   #
#    measured by this tool are not very precise.                             #
#    DF flag implementation is currently not supported on OS X and FreeBSD.  #
#                                                                            #
#  Not yet supported:                                                        #
#    - authenticated and encrypted mode                                      #
#    - sending intervals variation                                           #
#    - enhanced statistics                                                   #
#       => bining and interim statistics                                     #
#       => late arrived packets                                              #
#       => smokeping like graphics                                           #
#       => median on latency                                                 #
#       => improved jitter (rfc3393, statistical variance formula):          #
#          jitter:=sqrt(SumOf((D[i]-average(D))^2)/ReceivedProbesCount)      #
#    - daemon mode: NETCONF/YANG controlled, ...                             #
#    - enhanced failure handling (catch exceptions)                          #
#    - per probe time-out for statistics (late arrival)                      #
#    - Validation with other operating systems (such as FreeBSD)             #
#    - Support for RFC 5938 Individual Session Control                       #
#    - Support for RFC 6038 Reflect Octets Symmetrical Size                  #
#                                                                            #
##############################################################################

"""
TWAMP validation tool for Python
"""

#############################################################################

import os
import struct
import sys
import time
import socket
import logging
import binascii
import threading
import random
import argparse
import signal
import select

from twamp.constants import TIMEOFFSET, ALLBITS
from twamp.utils import now, parse_addr, time_ntp2py

#############################################################################

def zeros(nbr):
    return struct.pack('!%sB' % nbr, *[0 for x in range(nbr)])


def dp(ms):
    if abs(ms) > 60000:
        return "%7.1fmin" % float(ms / 60000)
    if abs(ms) > 10000:
        return "%7.1fsec" % float(ms / 1000)
    if abs(ms) > 1000:
        return "%7.2fsec" % float(ms / 1000)
    if abs(ms) > 1:
        return "%8.2fms" % ms
    return "%8dus" % int(ms * 1000)


#############################################################################


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
        self.running = False
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()


class twampStatistics():

    def __init__(self):
        self.count = 0

    def add(self, delayRT, delayOB, delayIB, rseq, sseq):
        if self.count == 0:
            self.minOB = delayOB
            self.minIB = delayIB
            self.minRT = delayRT

            self.maxOB = delayOB
            self.maxIB = delayIB
            self.maxRT = delayRT

            self.sumOB = delayOB
            self.sumIB = delayIB
            self.sumRT = delayRT

            self.lossIB = rseq
            self.lossOB = sseq - rseq

            self.jitterOB = 0
            self.jitterIB = 0
            self.jitterRT = 0

            self.lastOB = delayOB
            self.lastIB = delayIB
            self.lastRT = delayRT
        else:
            self.minOB = min(self.minOB, delayOB)
            self.minIB = min(self.minIB, delayIB)
            self.minRT = min(self.minRT, delayRT)

            self.maxOB = max(self.maxOB, delayOB)
            self.maxIB = max(self.maxIB, delayIB)
            self.maxRT = max(self.maxRT, delayRT)

            self.sumOB += delayOB
            self.sumIB += delayIB
            self.sumRT += delayRT

            self.lossIB = rseq - self.count
            self.lossOB = sseq - rseq

            if self.count == 1:
                self.jitterOB = abs(self.lastOB - delayOB)
                self.jitterIB = abs(self.lastIB - delayIB)
                self.jitterRT = abs(self.lastRT - delayRT)
            else:
                self.jitterOB = self.jitterOB + \
                    (abs(self.lastOB - delayOB) - self.jitterOB) / 16
                self.jitterIB = self.jitterIB + \
                    (abs(self.lastIB - delayIB) - self.jitterIB) / 16
                self.jitterRT = self.jitterRT + \
                    (abs(self.lastRT - delayRT) - self.jitterRT) / 16

            self.lastOB = delayOB
            self.lastIB = delayIB
            self.lastRT = delayRT

        self.count += 1

    def dump(self, total):
        print("===============================================================================")
        print("Direction         Min         Max         Avg          Jitter     Loss")
        print("-------------------------------------------------------------------------------")
        if self.count > 0:
            self.lossRT = total - self.count
            print("  Outbound:    %s  %s  %s  %s    %5.1f%%" % (dp(self.minOB), dp(self.maxOB), dp(self.sumOB / self.count), dp(self.jitterOB), 100 * float(self.lossOB) / total))
            print("  Inbound:     %s  %s  %s  %s    %5.1f%%" % (dp(self.minIB), dp(self.maxIB), dp(self.sumIB / self.count), dp(self.jitterIB), 100 * float(self.lossIB) / total))
            print("  Roundtrip:   %s  %s  %s  %s    %5.1f%%" % (dp(self.minRT), dp(self.maxRT), dp(self.sumRT / self.count), dp(self.jitterRT), 100 * float(self.lossRT) / total))
        else:
            print("  NO STATS AVAILABLE (100% loss)")
        print("-------------------------------------------------------------------------------")
        print("                                                    Jitter Algorithm [RFC1889]")
        print("===============================================================================")
        sys.stdout.flush()

#############################################################################


class SessionSender(udpSession):

    def __init__(self, args):
        # Session Sender / Session Reflector:
        #   get Address, UDP port, IP version from near_end/far_end attributes
        sip, spt, sipv = parse_addr(args.near_end, 20000)
        rip, rpt, ripv = parse_addr(args.far_end,  20001)

        ipversion = 6 if (sipv == 6) or (ripv == 6) else 4
        udpSession.__init__(self, sip, spt, args.tos, args.ttl, args.do_not_fragment, ipversion)

        self.remote_addr = rip
        self.remote_port = rpt
        self.interval = float(args.interval) / 1000
        self.count = args.count
        self.stats = twampStatistics()

        if args.padding != -1:
            self.padmix = [args.padding]
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
                pbytes = zeros(self.padmix[int(len(self.padmix) * random.random())])

                self.sendto(data + pbytes, (self.remote_addr, self.remote_port))
                logger.info("Sent to %s [sseq=%d]", self.remote_addr, idx)

                idx = idx + 1
                if schedule > t1:
                    r, w, e = select.select([self.socket], [], [], schedule - t1)

            if (t1 > endtime):
                logger.info("Receive timeout for last packet (don't wait anymore)")
                self.running = False

        self.stats.dump(idx)


class SessionReflector(udpSession):

    def __init__(self, args):
        addr, port, ipversion = parse_addr(args.near_end, 20001)

        if args.padding != -1:
            self.padmix = [args.padding]
        elif ipversion == 6:
            self.padmix = [0, 0, 0, 0, 0, 0, 0, 514, 514, 514, 514, 1438]
        else:
            self.padmix = [8, 8, 8, 8, 8, 8, 8, 534, 534, 534, 534, 1458]

        udpSession.__init__(self, addr, port, args.tos, args.ttl, args.do_not_fragment, ipversion)

    def run(self):
        index = {}
        reset = {}

        while self.running:
            try:
                data, address = self.recvfrom()

                t2 = now()
                sec = int(TIMEOFFSET + t2)             # seconds since 1-JAN-1900
                msec = int((t2 - int(t2)) * ALLBITS)  # 32bit fraction of the second

                sseq = struct.unpack('!I', data[0:4])[0]
                t1 = time_ntp2py(data[4:12])

                logger.info("Request from %s:%d [sseq=%d outbound=%.2fms]", address[0], address[1], sseq, 1000 * (t2 - t1))

                idx = 0
                if address not in index.keys():
                    logger.info("set rseq:=0     (new remote address/port)")
                elif reset[address] < t2:
                    logger.info("reset rseq:=0   (session timeout, 30sec)")
                elif sseq == 0:
                    logger.info("reset rseq:=0   (received sseq==0)")
                else:
                    idx = index[address]

                rdata = struct.pack('!L2I2H2I', idx, sec, msec, 0x001, 0, sec, msec)
                pbytes = zeros(self.padmix[int(len(self.padmix) * random.random())])
                self.sendto(rdata + data[0:14] + pbytes, address)

                index[address] = idx + 1
                reset[address] = t2 + 30  # timeout is 30sec

            except Exception as e:
                logger.debug('Exception: %s', str(e))
                break

        logger.info("TWL session reflector stopped")


class ControlClient:

    def __init__(self, server="", tcp_port=862, tos=0x88, ipversion=4):
        if ipversion == 6:
            self.connect6(server, tcp_port, tos)
        else:
            self.connect(server, tcp_port, tos)

    def connect(self, server="", port=862, tos=0x88):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos)
        self.socket.connect((server, port))

    def connect6(self, server="", port=862, tos=0x88):
        self.socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_TCLASS, tos)
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
        self.send(struct.pack('!I', 1) + zeros(160))

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
        request = struct.pack('!B', 2) + zeros(31)
        logger.info("CTRL.TX <<Start Sessions>>")
        self.send(request)
        logger.info("CTRL.RX <<Start Accept>>")
        self.receive()

    def stopSessions(self):
        request = struct.pack('!BBHLQQQ', 3, 0, 0, self.nbrSessions, 0, 0, 0)
        logger.info("CTRL.TX <<Stop Sessions>>")
        self.send(request)

        self.nbrSessions = 0

#############################################################################


def twl_sender(args):
    sender = twampySessionSender(args)
    sender.setDaemon(True)
    sender.setName("twl_responder")
    sender.start()

    signal.signal(signal.SIGINT, sender.stop)

    while sender.isAlive():
        time.sleep(0.1)


def twamp_controller(args):
    # Session Sender / Session Reflector:
    #   get Address, UDP port, IP version from near_end/far_end attributes
    sip, spt, ipv = parse_addr(args.near_end, 20000)
    rip, rpt, ipv = parse_addr(args.far_end,  20001)

    client = twampyControlClient(server=rip, ipversion=ipv)
    client.connectionSetup()

    if client.reqSession(s_port=spt, r_port=rpt):
        client.startSessions()

        sender = twampySessionSender(args)
        sender.setDaemon(True)
        sender.setName("twl_responder")
        sender.start()
        signal.signal(signal.SIGINT, sender.stop)

        while sender.isAlive():
            time.sleep(0.1)
        time.sleep(5)

        client.stopSessions()


def twamp_ctclient(args):
    # Session Sender / Session Reflector:
    #   get Address, UDP port, IP version from twamp sender/server attributes
    sip, spt, ipv = parse_addr(args.twl_send, 20000)
    rip, rpt, ipv = parse_addr(args.twserver, 20001)

    client = twampyControlClient(server=rip, ipversion=ipv)
    client.connectionSetup()

#    if client.reqSession(sender=sip, s_port=spt, receiver=rip, r_port=rpt):
    if client.reqSession(sender=sip, s_port=spt, receiver="0.0.0.0", r_port=rpt):
        client.startSessions()

        while True:
            time.sleep(0.1)

        client.stopSessions()

#############################################################################

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    # parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)

    subparsers = parser.add_subparsers(help='twampy sub-commands')

    # p_responder = subparsers.add_parser('responder', help='TWL responder', parents=[debug_parser, ipopt_parser])
    # group = p_responder.add_argument_group("TWL responder options")
    # group.add_argument('near_end', nargs='?', metavar='local-ip:port', default=":20001")
    # group.add_argument('--timer', metavar='value',   default=0,     type=int, help='TWL session reset')

    p_sender = subparsers.add_parser('sender', help='TWL sender', parents=[debug_parser, ipopt_parser])
    group = p_sender.add_argument_group("TWL sender options")
    group.add_argument('far_end', nargs='?', metavar='remote-ip:port', default="127.0.0.1:20001")
    group.add_argument('near_end', nargs='?', metavar='local-ip:port', default=":20000")
    group.add_argument('-i', '--interval', metavar='msec', default=100,  type=int, help="[100,1000]")
    group.add_argument('-c', '--count',    metavar='packets', default=100,  type=int, help="[1..9999]")

    p_control = subparsers.add_parser('controller', help='TWAMP controller', parents=[debug_parser, ipopt_parser])
    group = p_control.add_argument_group("TWAMP controller options")
    group.add_argument('far_end', nargs='?', metavar='remote-ip:port', default="127.0.0.1:20001")
    group.add_argument('near_end', nargs='?', metavar='local-ip:port', default=":20000")
    group.add_argument('-i', '--interval', metavar='msec', default=100,  type=int, help="[100,1000]")
    group.add_argument('-c', '--count',    metavar='packets', default=100,  type=int, help="[1..9999]")

    p_ctclient = subparsers.add_parser('controlclient', help='TWAMP control client', parents=[debug_parser, ipopt_parser])
    group = p_ctclient.add_argument_group("TWAMP control client options")
    group.add_argument('twl_send', nargs='?', metavar='twamp-sender-ip:port', default="127.0.0.1:20001")
    group.add_argument('twserver', nargs='?', metavar='twamp-server-ip:port', default=":20000")
    group.add_argument('-c', '--count',    metavar='packets', default=100,  type=int, help="[1..9999]")

    p_dscptab = subparsers.add_parser('dscptable', help='print DSCP table', parents=[debug_parser])

    # methods to call
    p_sender.set_defaults(parseop=True, func=twl_sender)
    p_control.set_defaults(parseop=True, func=twamp_controller)
    p_ctclient.set_defaults(parseop=True, func=twamp_ctclient)
    p_responder.set_defaults(parseop=True, func=twl_responder)
    # p_dscptab.set_defaults(parseop=False, func=dscpTable)


#############################################################################

    # if options.dscp:
    #     if options.dscp in dscpmap:
    #         options.tos = dscpmap[options.dscp]
    #     else:
    #         parser.error("Invalid DSCP Value '%s'" % options.dscp)

    # options.func(options)

# EOF