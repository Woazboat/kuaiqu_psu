#!/usr/bin/env python

# SPDX-License-Identifier: GPL-3.0-or-later

# kuaiquctl - control library and CLI for KUAIQU DC power supplies
# Copyright (C) 2025 Woazboat

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import logging
import sys
from time import sleep

_log = logging.getLogger(__name__)

import kuaiqu_psu


TIMEOUT = 1

def simple_test(psu: kuaiqu_psu.PowerSupply):
    psu.output(True)
    sleep(1)

    if not psu.set_voltage(5.15):
        _log.error('ERROR: Failed to set output voltage')
        return 1
    sleep(1)

    if not psu.set_current(0.250):
        _log.error('ERROR: Failed to set output current limit')
        return 1
    sleep(1)

    v = psu.read_voltage()
    if not v:
        _log.error('ERROR: Failed to read voltage')
        return 1
    else:
        _log.info(f'Voltage: {v}')
    c = psu.read_current()
    if not c:
        _log.error('ERROR: Failed to read current')
        return 1
    _log.info(f'Current: {c}')
    sleep(1)

    if not psu.lock_buttons(True):
        _log.error('ERROR: Failed to lock buttons')
        return 1
    sleep(1)

    if not psu.set_current(0.100):
        _log.error('ERROR: Failed to set output current limit')
        return 1
    sleep(1)

    if not psu.set_voltage(3.3):
        _log.error('ERROR: Failed to set output voltage')
        return 1
    sleep(2)

    if not psu.lock_buttons(False):
        _log.error('ERROR: Failed to unlock buttons')
        return 1
    sleep(1)

    psu.output(False)
    sleep(1)

    if not psu.set_voltage(0):
        _log.error('ERROR: Failed to set output voltage')
        return 1
    
    if not psu.set_current(0):
        _log.error('ERROR: Failed to set output current limit')
        return 1

    return 0

def kuaiquctl():
    parser = argparse.ArgumentParser()

    parser.add_argument('serial_port', type=str)

    group = parser.add_argument_group('Power supply output options')
    group.add_argument('-v', '-u', '--volt', type=float, help='Set the output voltage')
    group.add_argument('-a', '-c', '-i', '--ampere', '--current', type=float, help='Set the output current limit')

    enable_group = group.add_mutually_exclusive_group()
    enable_group.add_argument('-e', '--enable', action='store_true', help='Enable output')
    enable_group.add_argument('-d', '--disable', action='store_true', help='Disable output')

    parser.add_argument('--run_test', action='store_true', help='Run simple functionality test (WARNING: enables PSU output)')

    verbose_group = group.add_mutually_exclusive_group()
    verbose_group.add_argument('--verbose', action='store_true')
    verbose_group.add_argument('--quiet', action='store_true')

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(message)s')
    elif args.quiet:
        logging.basicConfig(level=logging.WARNING, format='%(message)s')

    with kuaiqu_psu.PowerSupply(args.serial_port, max_current=None, max_voltage=None) as psu:
        if not args.run_test:
                if args.volt is not None:
                    status = psu.set_voltage(args.volt)
                    if not status:
                        _log.error('ERROR: Failed to set output voltage')
                        return 1

                if args.ampere is not None:
                    status = psu.set_current(args.ampere)
                    if not status:
                        _log.error('ERROR: Failed to set output current limit')
                        return 1

                if args.enable:
                    psu.output(True)
                elif args.disable:
                    psu.output(False)

        else:
            return simple_test(psu)

        return 0


if __name__ == '__main__':
    sys.exit(kuaiquctl())
