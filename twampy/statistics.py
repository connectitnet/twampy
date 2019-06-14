import click

from twampy.utils import format_time


class twampStatistics:

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
        click.echo(
            "===============================================================================")
        click.echo(
            "Direction         Min         Max         Avg          Jitter     Loss")
        click.echo(
            "-------------------------------------------------------------------------------")
        if self.count > 0:
            self.lossRT = total - self.count
            click.echo("  Outbound:    %s  %s  %s  %s    %5.1f%%" % (
                format_time(self.minOB),
                format_time(self.maxOB),
                format_time(self.sumOB / self.count),
                format_time(self.jitterOB),
                100 * float(self.lossOB) / total))
            click.echo("  Inbound:     %s  %s  %s  %s    %5.1f%%" % (
                format_time(self.minIB),
                format_time(self.maxIB),
                format_time(self.sumIB / self.count),
                format_time(self.jitterIB),
                100 * float(self.lossIB) / total))
            click.echo("  Roundtrip:   %s  %s  %s  %s    %5.1f%%" % (
                format_time(self.minRT),
                format_time(self.maxRT),
                format_time(self.sumRT / self.count),
                format_time(self.jitterRT),
                100 * float(self.lossRT) / total))
        else:
            click.echo("  NO STATS AVAILABLE (100% loss)", err=True)
        click.echo(
            "-------------------------------------------------------------------------------")
        click.echo(
            "                                                    Jitter Algorithm [RFC1889]")
        click.echo(
            "===============================================================================")
