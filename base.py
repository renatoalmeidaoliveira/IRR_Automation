from pyats import aetest
from utils import (
    createBackup,
    getLastBackup,
    rollbackDevice,)
import logging

logger = logging.getLogger(__name__)


class BaseSetup(aetest.CommonSetup):

    @aetest.subsection
    def connect_to_devices(self, testbed):
        for device in testbed:
            try:
                device.connect(alias='nc', via='netconf')
                device.changed = False
                device.failed =  False
            except Exception as e:
                self.errored(
                    reason=f"Failed to connect {device.name}",
                    goto=['exit'],
                    from_exception=e)

    @aetest.subsection
    def backup_devices(self, testbed):
        for device in testbed:
            try:
                createBackup(device)
            except Exception as e:
                self.errored(
                    reason=f"Failed Backup {device.name}",
                    goto=['exit'],
                    from_exception=e,)

    @aetest.subsection
    def set_backup_path(self, testbed):
        for device in testbed:
            try:
                device.backup_path = getLastBackup(device)
            except Exception as e:
                self.errored(
                    reason=f"Failed to set Backup path on {device.name}",
                    goto=['exit'],
                    from_exception=e,)


class BaseCleanup(aetest.CommonCleanup):


    @aetest.subsection
    def check_execution(self, testbed):
        self.parameters['rollback'] = False
        for device in testbed:
            if(device.failed is True):
                self.parameters['rollback'] = True
                break

    @aetest.subsection
    def rollback_all(self, testbed):
        if(self.parameters['rollback'] is True):
            for device in testbed:
                if(device.changed is True):
                    backup_path = device.backup_path
                    reply = rollbackDevice(device=device, path=backup_path)
                    logger.info(reply)
        else:
            self.skipped("All tests passed")

    @aetest.subsection
    def disconnect_all(self, testbed):
        for device in testbed:
            device.nc.disconnect()

