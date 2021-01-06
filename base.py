from pyats import aetest
from utils import (
    create_backup,
    get_backup_path,
    restore_device,)
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
                create_backup(device)
                backup_path = get_backup_path(device)
                device.backup_path = backup_path
            except Exception as e:
                self.errored(
                    reason=f"Failed Backup {device.name}",
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
            try:
                for device in testbed:
                    if(device.changed is True):
                        backup_path = device.backup_path
                        restore_device(device, device.backup_path)
            except Exception as e:
                self.errored(
                    reason=f"Failed to rollback {device.name}",
                    from_exception=e,)
        else:
            self.skipped("All tests passed")

    @aetest.subsection
    def disconnect_all(self, testbed):
        for device in testbed:
            device.nc.disconnect()

