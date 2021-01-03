from pyats import aetest
from base import (
    BaseSetup,
    BaseCleanup,)
from utils import (
    getASSet,
    getASPrefixes,
    createPrefixListPayload,
    getConfiguredPrefixesFilter)
import logging
import xmltodict
import time


class Setup(BaseSetup):

    @aetest.subsection
    def configure_prefix_list(self, testbed):
        as_set = getASSet(asn=109)
        prefixes = getASPrefixes(as_set, 4, aggregate=True)
        payload = createPrefixListPayload(name=as_set, prefixes=prefixes)
        for device in testbed:
            try:
                device.nc.edit_config(target='running', config=payload)
                device.changed = True
            except Exception as e:
                device.failed = True
                self.errored(
                    reason=f"Failed to configure Prefix List on {device.name}",
                    goto=['common_cleanup'],
                    from_exception=e,)


class ConfigurationTest(aetest.Testcase):

    @aetest.test
    def check_configured_object(self, testbed):
        for device in testbed:
            try:
                payload = getConfiguredPrefixesFilter(asn=109)
                configured_prefixes = device.nc.get_config(
                    source='running', filter=payload)
                configObject = xmltodict.parse(configured_prefixes.data_xml)
                conf_prefixes = configObject['data']['native']['ip']['prefix-list']['prefixes']['seq']
                as_set = getASSet(asn=109)
                expect_prefixes = getASPrefixes(as_set, 4, aggregate=True)
                expected_len = 0
                for prefix in expect_prefixes:
                    existPrefix = False
                    correctPrefix = False
                    for confPrefix in conf_prefixes:
                        if(prefix['exact'] is True):
                            if (prefix['prefix'] == confPrefix['ip']) and \
                               ('le' not in confPrefix) and \
                               ('ge' not in confPrefix):

                                existPrefix = True
                                correctPrefix = True
                                conf_prefixes.remove(confPrefix)
                                expected_len = expected_len + 1
                        else:
                            if prefix['prefix'] == confPrefix['ip']:
                                existPrefix = True
                                if('less-equal' in prefix):
                                    if('le' in confPrefix):
                                        if(str(prefix['less-equal']) == str(confPrefix['le'])):
                                            correctPrefix = True
                                if('greater-equal' in prefix):
                                    if('ge' in confPrefix):
                                        if(str(prefix['greater-equal']) == str(confPrefix['ge'])):
                                            correctPrefix = True
                                conf_prefixes.remove(confPrefix)
                                expected_len = expected_len + 1
                    assert (existPrefix is True)
                    assert (correctPrefix is True)
                assert expected_len == len(expect_prefixes)
                assert len(conf_prefixes) == 0
            except Exception as e:
                device.failed = True
                self.errored(
                    reason=f"Incorrect configuration on {device.name}",
                    goto=['common_cleanup'],
                    from_exception=e,)

    @aetest.test
    def wait_for_update(self, testbed):
        time.sleep(60)

    @aetest.test
    def check_installed_prefixes_number(self, testbed):
        for device in testbed:
            try:
                netconf_filter = """
                    <filter>
                      <bgp-state-data>
                        <neighbors>
                          <neighbor>
                            <neighbor-id>{neighbor}</neighbor-id>
                          </neighbor>
                        </neighbors>
                      </bgp-state-data>
                    </filter>"""
                reply = device.nc.get(
                    filter=netconf_filter.format(neighbor="172.30.0.1"))
                data = xmltodict.parse(reply.data_xml)
                installedPrefixesNumber = data['data']['bgp-state-data']['neighbors']['neighbor']['prefix-activity']['received']['current-prefixes']
                as_set = getASSet(asn=109)
                expect_prefixes = getASPrefixes(as_set, 4)
                assert int(installedPrefixesNumber) <= len(expect_prefixes)
            except Exception as e:
                device.failed = True
                expected_len = len(expect_prefixes)
                self.errored(
                    reason=f"The number of installed prefixes {installedPrefixesNumber} is greater than expected {expected_len} on {device.name}",
                    goto=['common_cleanup'],
                    from_exception=e,)


    @aetest.test
    def check_installed_prefixes(self, testbed):
        for device in testbed:
            try:
                as_set = getASSet(asn=109)
                expect_prefixes = getASPrefixes(as_set, 4, aggregate=False)
                netconf_filter = """
                <filter>
                  <bgp-state-data>
                    <bgp-route-vrfs>
                      <bgp-route-vrf>
                        <bgp-route-afs>
                          <bgp-route-af>
                           <afi-safi>ipv4-unicast</afi-safi>
                            <bgp-route-neighbors>
                               <bgp-route-neighbor>
                                 <nbr-id>{neighbor}</nbr-id>
                               </bgp-route-neighbor>
                            </bgp-route-neighbors>
                          </bgp-route-af>
                        </bgp-route-afs>
                      </bgp-route-vrf>
                    </bgp-route-vrfs>
                  </bgp-state-data>
                </filter>"""
                reply = device.nc.get(
                    filter=netconf_filter.format(neighbor="172.30.0.1"))
                data = xmltodict.parse(reply.data_xml)
                bgpRouteFilters = data['data']['bgp-state-data']['bgp-route-vrfs']['bgp-route-vrf']['bgp-route-afs']['bgp-route-af']['bgp-route-neighbors']['bgp-route-neighbor']['bgp-neighbor-route-filters']['bgp-neighbor-route-filter']
                if('bgp-neighbor-route-entries' in bgpRouteFilters):                    
                    prefixes = bgpRouteFilters['bgp-neighbor-route-entries']['bgp-neighbor-route-entry']
                    istalledPrefixes = []
                    if(isinstance(prefixes, list)):
                        for prefix in prefixes:
                            istalledPrefixes.append(prefix['prefix'])
                    else:
                        istalledPrefixes.append(prefixes['prefix'])
                    expect_prefixes_list = []
                    for prefix in expect_prefixes:
                        expect_prefixes_list.append(prefix['prefix'])
                    existIncorrectPrefix = False
                    logger.info(expect_prefixes_list)
                    logger.info(istalledPrefixes)
                    for prefix in istalledPrefixes:
                        if prefix not in expect_prefixes_list:
                            logger.info(prefix)
                            existIncorrectPrefix = True
                    assert existIncorrectPrefix is not True
                else:
                    self.passx(reason="No prefix Installed")
            except Exception as e:
                device.failed = True
                self.errored(
                    reason=f"Found unexpected prefix on {device.name}",
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


