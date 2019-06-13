import time
import sys
import struct


from twamp.constants import TIMEOFFSET, ALLBITS

def parse_addr(addr, port=20000):
    """ Parse IP addresses and ports.
        Works with:
            IPv6 address with and without port;
            IPv4 address with and without port.
    """
    if addr == '':
        # no address given (default: localhost IPv4 or IPv6)
        return "", port, 0
    elif ']:' in addr:
        # IPv6 address with port
        ip, port = addr.rsplit(':', 1)
        return ip.strip('[]'), int(port), 6
    elif ']' in addr:
        # IPv6 address without port
        return addr.strip('[]'), port, 6
    elif addr.count(':') > 1:
        # IPv6 address without port
        return addr, port, 6
    elif ':' in addr:
        # IPv4 address with port
        ip, port = addr.split(':')
        return ip, int(port), 4
    else:
        # IPv4 address without port
        return addr, port, 4


def now():
    if (sys.platform == "win32"):
        time0 = time.time() - time.clock()
        return time.clock() + time0
    return time.time()


def time_ntp2py(data):
    """
    Convert NTP 8 byte binary format [RFC1305] to python timestamp
    """

    ta, tb = struct.unpack('!2I', data)
    t = ta - TIMEOFFSET + float(tb) / float(ALLBITS)
    return t
