import click
import click_log
import click_spinner
import os
import sys
import functools

from logging.handlers import TimedRotatingFileHandler

import logging
logger = logging.getLogger(__name__)
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
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))


def ip_params(func):
    @click.option("--tos", metavar="<type-of-service>", default="0x88", type=HexParamType(), help='IP TOS value in hex format. ex.: 0x88')
    @click.option("--dscp", metavar="<dscp-value>", help='IP DSCP value')
    @click.option("--ttl", metavar="<time-to-live>", default=64, type=click.IntRange(1, 128), help='[1..128]')
    @click.option("--padding", metavar="<bytes>", default=0, type=int, help='IP/UDP mtu value')
    @click.option("--do-not-fragment",  is_flag=True, help='Set do-not-fragment flag on IP packets')
    @functools.wraps(func)
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

# sender
@cli.command()
@ip_params
def sender(tos, dscp, ttl, padding, do_not_fragment):
    pass

# controller
@cli.command()
def controller(tos, dscp, ttl, padding, do_not_fragment):
    pass

# client
@cli.command()
def client(tos, dscp, ttl, padding, do_not_fragment):
    pass

# responder
@cli.command()
@click.argument('near_end', metavar='local-ip:port', default=":20001")
@click.option('--timer', metavar='value', default=0, type=int, help='TWL session reset')
@ip_params
def responder(near_end, timer, tos, dscp, ttl, padding, do_not_fragment):
    reflector = SessionReflector(args)
    reflector.setDaemon(True)
    reflector.setName("twl_responder")
    reflector.start()

    signal.signal(signal.SIGINT, reflector.stop)

    while reflector.isAlive():
        time.sleep(0.1)


if __name__ == "__main__":
    cli()


# with click_spinner.spinner():
    # do_something()
    # do_something_else()
