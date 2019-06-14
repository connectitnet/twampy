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
#  License:                                                                  #
#    Licensed under the BSD license                                          #
#    See LICENSE.md delivered with this project for more information.        #
#                                                                            #
#  Original author:                                                          #
#    Sven Wisotzky                                                           #
#    mail:  sven.wisotzky(at)nokia.com                                       #
##############################################################################