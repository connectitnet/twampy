#!/usr/bin/env python3

from twampy.constants import DSCP_MAP, INTERVAL_DEFAULT, TTL_DEFAULT, TOS_DEFAULT, DSCP_DEFAULT, COUNT_DEFAULT, PADDING_DEFAULT, TWAMP_PORT_DEFAULT
from twampy.controlclient import ControlClient
from twampy.sessionreflector import SessionReflector
from twampy.sessionsender import SessionSender
from twampy.utils import parse_addr

import click
import click_log
import os
import signal
import sys
import time
import functools

from logging.handlers import TimedRotatingFileHandler


import logging
logger = logging.getLogger("twampy")
click_logger = click_log.basic_config(logger)


class HexParamType(click.ParamType):
    name = 'hex'

    def convert(self, value, param, ctx):
        try:
            return int(value, 16)
        except (ValueError, UnicodeError):
            self.fail('%s is not valid hexadecimal' % value, param, ctx)

    def __repr__(self):
        return 'HEX'


class AliasedGroup(click.Group):

    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [x for x in self.list_commands(ctx)
                   if x.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail('Please be more specific \n%s' % '\n'.join(sorted(matches)))


near_end_argument = click.argument(
    'near_end', metavar='local-ip:port', default=":%d" % TWAMP_PORT_DEFAULT)
count_option = click.option('-c', '--count', metavar='packets', default=COUNT_DEFAULT,
                            type=click.IntRange(1, 9999, True), help="[1..9999]")


def ip_options(func):
    @click.option("--tos", metavar="<type-of-service>", default=str(TOS_DEFAULT), type=HexParamType(), help='IP TOS value in hex format. ex.: 0x88')
    @click.option("--dscp", metavar="<dscp-value>", type=click.Choice(DSCP_MAP.keys()), default='be', help='IP DSCP value')
    @click.option("--ttl", metavar="<time-to-live>", default=TTL_DEFAULT, type=click.IntRange(1, 128), help='[1..128]')
    # TODO: CONFIRM THIS
    @click.option("--padding", metavar="<bytes>", default=PADDING_DEFAULT, type=int, help='IP/UDP packet size')
    @click.option("--do-not-fragment",  is_flag=True, help='Set do-not-fragment flag on IP packets')
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


def twampy_params(func):
    @near_end_argument
    @click.argument('far_end', metavar='remote-ip:port', default="127.0.0.1:%d" % TWAMP_PORT_DEFAULT)
    @count_option
    @click.option('-i', '--interval', metavar='msec', default=INTERVAL_DEFAULT,  type=click.IntRange(100, 1000, True), help="[100,1000]")
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


@click.group(cls=AliasedGroup)
@click_log.simple_verbosity_option(logger)
@click.option("-q", "--quiet", "quiet", is_flag=True)
@click.option("-l", "--logfile", "logfile", type=click.Path())
def cli(quiet, logfile):
    """Python implementation of the Two-Way Active Measurement Protocol
       (TWAMP and TWAMP light) as defined in RFC5357."""

    loglevel = logger.level
    if quiet:
        logger.setLevel(logging.NOTSET)

    if loglevel >= logging.DEBUG and logfile:
        file_handler = TimedRotatingFileHandler(
            filename=logfile, when='midnight', backupCount=31)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        file_handler.setLevel(loglevel)
        click_logger.addHandler(file_handler)

# TODO: sender
# @cli.command('sender')
@twampy_params
@ip_options
def sender(tos, dscp, ttl, padding, do_not_fragment):
    # sender = SessionSender(args)
    # sender.setDaemon(True)
    # sender.setName("twl_responder")
    # sender.start()

    # signal.signal(signal.SIGINT, sender.stop)

    # while sender.isAlive():
    #     time.sleep(0.1)
    pass


# TODO: server
# @cli.command('server')
@twampy_params
@ip_options
def controller(near_end, far_end, count, interval, tos, dscp, ttl, padding, do_not_fragment):
    # sip, spt, ipv = parse_addr(near_end, TWAMP_PORT_DEFAULT)
    # rip, rpt, ipv = parse_addr(far_end,  TWAMP_PORT_DEFAULT)

    # client = ControlClient(server=rip, ipversion=ipv)
    # client.connectionSetup()

    # if client.reqSession(s_port=spt, r_port=rpt):
    #     client.startSessions()

    #     # sender = SessionSender(args)
    #     sender.setDaemon(True)
    #     sender.setName("twl_responder")
    #     sender.start()
    #     signal.signal(signal.SIGINT, sender.stop)

    #     while sender.isAlive():
    #         time.sleep(0.1)
    #     time.sleep(5)

    #     client.stopSessions()
    pass

# TODO: client
# @cli.command('client')
@click.argument('sender', metavar='twamp-sender-ip:port', default="127.0.0.1:%d" % TWAMP_PORT_DEFAULT)
@click.argument('server', metavar='twamp-server-ip:port', default="%d" % TWAMP_PORT_DEFAULT)
def controlclient(sender, server):
    # with click_spinner.spinner():
    #     # Session Sender / Session Reflector:
    #     #  get Address, UDP port, IP version from twamp sender/server attributes
    #     sip, spt, ipv = parse_addr(sender, TWAMP_CTRL_PORT_DEFAULT)
    #     rip, rpt, ipv = parse_addr(server, TWAMP_PORT_DEFAULT)

    #     client = ControlClient(server=rip)
    #     client.connectionSetup()

    # #    if client.reqSession(sender=sip, s_port=spt, receiver=rip, r_port=rpt):
    #     if client.reqSession(sender=sip, s_port=spt, receiver="0.0.0.0", r_port=rpt):
    #         client.startSessions()

    #         while True:
    #             time.sleep(0.1)

    #         client.stopSessions()
    pass

# responder
@cli.command('reflector')
@near_end_argument
def reflector(near_end):

    reflector = SessionReflector(near_end)
    reflector.setDaemon(True)
    reflector.setName("twl_reflector")
    reflector.start()

    signal.signal(signal.SIGINT, reflector.stop)
    
    while reflector.isAlive():
        time.sleep(0.1)


if __name__ == "__main__":
    cli()


# with click_spinner.spinner():
    # do_something()
    # do_something_else()
