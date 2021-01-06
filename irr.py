from pyats import aetest
from base import (
    BaseSetup,
    BaseCleanup,)
from utils import (
    get_as_set,
    get_as_set_prefixes,
    create_prefix_list_payload,
    get_configured_prefixes,
    get_as_set_prefixes_list,
    get_neighbor_installed_prefixes,
    )
import logging
import xmltodict
import time


class Setup(BaseSetup):

    @aetest.subsection
    def configure_prefix_list(self, testbed):
            for device in testbed:
                try:
                    for neighbor in device.custom['neighbors']:
                        asn = neighbor['asn']
                        as_set = get_as_set(asn)
                        assert isinstance(as_set, str)
                        assert as_set != ''

                        prefixes = get_as_set_prefixes(as_set, 4 , aggregate=True)
                        assert isinstance(prefixes, list)
                        assert len(prefixes) > 0

                        payload = create_prefix_list_payload(name=as_set, prefixes=prefixes)
                        device.nc.edit_config(target='running', config=payload)
                        device.changed = True
                except Exception as e:
                    device.failed = True
                    self.errored(
                            reason=f"Failed execution on {device} and ASN {asn}",
                            goto=['common_cleanup'],
                            from_exception=e,)
                    



class configuration_tests(aetest.Testcase):

    @aetest.test
    def check_configured_object(self, testbed):
        for device in testbed:
            for neighbor in device.custom['neighbors']:
                asn = neighbor['asn']
                try:
                    as_set = get_as_set(asn)
                    assert isinstance(as_set, str)
                    assert as_set != ''

                    expected_prefixes = get_as_set_prefixes(as_set, 4, aggregate=True)
                    assert isinstance(expected_prefixes, list)
                    assert len(expected_prefixes) > 0

                    configured_prefixes = get_configured_prefixes(as_set, device)
                    assert isinstance(configured_prefixes, list)
                    assert len(configured_prefixes) > 0

                    assert len(expected_prefixes) == len(configured_prefixes)

                    for prefix in configured_prefixes:
                        assert prefix in expected_prefixes
                except Exception as e:
                    device.failed = True
                    self.errored(
                        reason=f"Incorrect configuration on  {device} and ASN {asn}",
                        goto=['common_cleanup'],
                        from_exception=e,)
         

    @aetest.test
    def wait_for_update(self, testbed):
        time.sleep(60)

    @aetest.test
    def check_installed_prefixes(self, testbed):
        for device in testbed:
            for neighbor in device.custom['neighbors']:
                try:

                    remote_address = neighbor['remote_address']
                    asn = neighbor['asn']

                    as_set = get_as_set(asn)
                    assert isinstance(as_set, str)
                    assert as_set != ''

                    expected_prefixes = get_as_set_prefixes_list(as_set, 4)
                    assert isinstance(expected_prefixes, list)
                    assert len(expected_prefixes) > 0

                    installed_prefixes = get_neighbor_installed_prefixes(device, 'ipv4-unicast', remote_address)
                    assert isinstance(installed_prefixes, list)

                    assert len(expected_prefixes) >= len(installed_prefixes)

                    for prefix in installed_prefixes:
                        assert prefix in expected_prefixes

                except Exception as e:
                    device.failed = True
                    self.errored(
                        reason=f"Incorrect prefixes of {remote_address} on {device}",
                        goto=['common_cleanup'],
                        from_exception=e,)

class Cleanup(BaseCleanup):
    pass


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if __name__ == '__main__':
    # for stand-alone execution
    import argparse
    from pyats import topology

    parser = argparse.ArgumentParser(description="standalone parser")
    parser.add_argument('--testbed', dest='testbed',
                        help='testbed YAML file',
                        type=topology.loader.load,
                        default=None)

    # do the parsing
    args = parser.parse_known_args()[0]

    aetest.main(testbed=args.testbed)


