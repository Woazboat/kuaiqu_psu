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

from contextlib import AbstractContextManager
from dataclasses import dataclass
from enum import Enum, StrEnum
import math
from typing import Any
import serial
import logging

_log = logging.getLogger(__name__)


_TIMEOUT = 1

def _split_int_fractional(f: float):
    return int(f), f % 1


class PowerSupply(AbstractContextManager[Any]):

    port: serial.Serial
    max_voltage: float | None
    max_current: float | None

    _close_port: bool


    @dataclass
    class Command:
        address: str = '0'
        function: str = '2'
        data1: str = '000'
        data2: str = '000'
        device: str = '000'

        class Function(StrEnum):
            SET_VOLTAGE = '1'
            READ_VOLTAGE = '2'
            SET_CURRENT = '3'
            READ_CURRENT = '4'
            ENABLE_OUTPUT = '7'
            DISABLE_OUTPUT = '8'
            LOCK = '9'

        class LockData1(StrEnum):
            LOCK = '100'
            UNLOCK = '200'
        
        def encode(self):
            return f'<{self.address:1}{self.function:1}{self.data1:03}{self.data2:03}{self.device:03}>'.encode()
        
        @staticmethod
        def from_str(s: str):
            assert s
            assert len(s)== 13
            assert s[0] == '<'
            assert s[-1] == '>'
            return PowerSupply.Command(address=s[1], function=s[2], data1=s[3:6], data2=s[6:9], device=s[9:12])
        
        @staticmethod
        def from_bytes(b: bytes):
            assert b
            assert len(b)== 13
            assert b[0:1] == b'<'
            assert b[-1:] == b'>'
            return PowerSupply.Command.from_str(b.decode())

        def is_ok_rsp(self):
            return self.data1 == 'OK0'


    class Mode(Enum):
        CONSTANT_VOLTAGE = '1'
        CONSTANT_CURRENT = 'C'


    def __init__(self, port: serial.Serial|str, max_voltage: int|None = 60, max_current: int|None = 5):
        self._close_port = False
        self.max_voltage = max_voltage
        self.max_current = max_current

        if isinstance(port, str):
            self.port = serial.Serial(port=port, baudrate=9600, timeout=_TIMEOUT, write_timeout=_TIMEOUT)
            self._close_port = True
        else:
            self.port = port


    def __enter__(self):
        return self
    

    def __exit__(self, *args, **kwargs) -> bool | None: # type: ignore
        if self._close_port:
            self.close()
        return super().__exit__(*args, **kwargs) # type: ignore
    

    def close(self):
        self.port.close()


    def send_cmd(self, cmd: Command, read_response: bool = True):
        cmd_data = cmd.encode()
        _log.debug(f"CMD -> {cmd_data} = {cmd}")
        self.port.write(cmd_data)
        if read_response:
            rsp_data = self.port.read_until(b'>')
            if rsp_data:
                rsp_cmd = PowerSupply.Command.from_bytes(rsp_data)
                _log.debug(f"RSP <- {rsp_data} = {rsp_cmd}")
                return rsp_cmd


    def output(self, enable: bool):
        _log.info(f'Set output: {enable}')
        # No response for output enable/disable command
        self.send_cmd(PowerSupply.Command(function=PowerSupply.Command.Function.ENABLE_OUTPUT if enable else PowerSupply.Command.Function.DISABLE_OUTPUT), read_response=False)


    def set_voltage(self, voltage: float):
        assert math.isfinite(voltage)
        assert voltage >= 0

        if self.max_voltage is not None and voltage > self.max_voltage:
            _log.warning(f'WARNING: Requested voltage {voltage} > maximum voltage {self.max_voltage}')
            voltage = min(voltage, self.max_voltage)

        _log.info(f'Set voltage: {voltage}V')

        int_part, fractional_part = _split_int_fractional(voltage)
        fractional_part = int(fractional_part*1000)

        cmd = PowerSupply.Command(function=PowerSupply.Command.Function.SET_VOLTAGE, data1=f'{int_part:03}', data2=f'{fractional_part:03}')
        return self.send_cmd(cmd)


    def set_current(self, current: float):
        assert math.isfinite(current)
        assert current >= 0

        if self.max_current is not None and current > self.max_current:
            _log.warning(f'WARNING: Requested current {current} > maximum current {self.max_current}')
            current = min(current, self.max_current)

        _log.info(f'Set current: {current}A')

        int_part, fractional_part = _split_int_fractional(current)
        fractional_part = int(fractional_part*1000)

        cmd = PowerSupply.Command(function=PowerSupply.Command.Function.SET_CURRENT, data1=f'{int_part:03}', data2=f'{fractional_part:03}')
        return self.send_cmd(cmd)


    # Should be correct according to documentation, but returned data did not really make sense on the tested unit
    # Returned constant voltage/current mode is correct
    def read_voltage(self):
        _log.info(f'Read voltage')
        cmd = PowerSupply.Command(function=PowerSupply.Command.Function.READ_VOLTAGE)
        rsp = self.send_cmd(cmd)
        if rsp:
            voltage = int(rsp.data1) + int(rsp.data2) / 1000.0
            _log.info(f'Voltage: {voltage}')
            return voltage, PowerSupply.Mode.CONSTANT_VOLTAGE if rsp.address == '1' else PowerSupply.Mode.CONSTANT_CURRENT
        return None


    # Should be correct according to documentation, but returned data did not really make sense on the tested unit
    # Returned constant voltage/current mode is correct
    def read_current(self):
        _log.info(f'Read current')
        cmd = PowerSupply.Command(function=PowerSupply.Command.Function.READ_CURRENT)
        rsp = self.send_cmd(cmd)
        if rsp:
            current = int(rsp.data1) + int(rsp.data2) / 1000.0
            _log.info(f'Current: {current}')
            return current, PowerSupply.Mode.CONSTANT_VOLTAGE if rsp.address == '1' else PowerSupply.Mode.CONSTANT_CURRENT
        return None


    def lock_buttons(self, lock: bool):
        _log.info(f'Set button lock: {lock}')
        return self.send_cmd(PowerSupply.Command(function=PowerSupply.Command.Function.LOCK, data1=(PowerSupply.Command.LockData1.LOCK if lock else PowerSupply.Command.LockData1.UNLOCK)))

