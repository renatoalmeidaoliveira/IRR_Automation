from pytanga.components import configComponent
from pytanga.components import filterComponent
from pytanga.components import rpcComponent

from pytanga.components.Cisco.xe import nativeComponent
from pytanga.components.Cisco.xe import saveConfigComponent
from pytanga.components.Cisco.xe import checkpointComponent
from pytanga.components.Cisco.xe import rollbackComponent

from pytanga.components.Cisco.xe.ip import ipComponent
from pytanga.components.Cisco.xe.ip import prefixeslistsComponent

from pytanga.helpers.Cisco.xe import ConfigurePrefixList

from pytanga.visitors import NETCONFVisitor

import subprocess
import requests
import json
import xmltodict


def get_as_set(asn):
    request = requests.get(
            "https://www.peeringdb.com/api/net?asn=" + str(asn))
    request.raise_for_status()
    response = json.loads(request.text)
    return response['data'][0]['irr_as_set']


def get_as_set_prefixes(as_set, ip_version, aggregate=None,):
    args = ["bgpq4", "-j"]
    if(ip_version == 4 or ip_version == 6):
        args.append("-" + str(ip_version))
    else:
        raise Exeption("Incorrect IP version")
    if(aggregate):
        args.append("-A")
    args.append("-lirr_prefix")
    args.append(as_set)
    process = subprocess.run(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if(process.returncode != 0):
        raise Exception(f"BGPq4 failed:\n{str(process.stderr)}")
    output = json.loads(process.stdout)
    return output['irr_prefix']


def create_prefix_list_payload(name, prefixes):
    helper = ConfigurePrefixList(name=name, replace=True)

    for prefix in prefixes:
        if(prefix['exact'] is True):
            helper.addPrefix(action='permit', network=prefix['prefix'])
        else:
            args = {
                'action': 'permit',
                'network': prefix['prefix']
            }
            if('less-equal' in prefix):
                args['le'] = prefix['less-equal']
            if('greater-equal' in prefix):
                args['ge'] = prefix['greater-equal']
            helper.addPrefix(**args)

    config = configComponent()
    native = nativeComponent()
    ip = ipComponent()
    prefix_list = helper.getPrefixList()

    config.add(native)
    native.add(ip)
    ip.add(prefix_list)
    serializer = NETCONFVisitor()
    output = config.parse(serializer)
    xml_string = serializer.print(output)
    return xml_string


def get_configured_prefixes(as_set, device):
    filter_component = filterComponent()
    native_component = nativeComponent()
    ip_component = ipComponent()
    helper = ConfigurePrefixList(name=as_set)
    prefix_list_component = helper.getPrefixList()

    filter_component.add(native_component)
    native_component.add(ip_component)
    ip_component.add(prefix_list_component)
    serializer = NETCONFVisitor()
    output = filter_component.parse(serializer)
    filter_payload = serializer.print(output)

    configured_prefixes = device.nc.get_config(
                    source='running', filter=filter_payload)
    configObject = xmltodict.parse(configured_prefixes.data_xml)
    conf_prefixes = configObject['data']['native']['ip']['prefix-list']['prefixes']['seq']
    prefixes = []
    if(isinstance(conf_prefixes, list)):
        for prefix in conf_prefixes:
            prefix_object = {
                'prefix': prefix['ip']
            }
            if(('le' in prefix) or ('ge' in prefix)):
                prefix_object['exact'] = False
                if('le' in prefix):
                    prefix_object['less-equal'] = int(prefix['le'])
                if('ge' in prefix):
                    prefix_object['greater-equal'] = int(prefix['ge'])
            else:
                prefix_object['exact'] = True
            prefixes.append(prefix_object)
    else:
        prefix = conf_prefixes
        prefix_object = {
            'prefix': prefix['ip']
        }
        if(('le' in prefix) or ('ge' in prefix)):
            prefix_object['exact'] = True
            if('le' in prefix):
                prefix_object['less-equal'] = int(prefix['le'])
            if('ge' in prefix):
                prefix_object['greater-equal'] = int(prefix['ge'])
        else:
            prefix_object['exact'] = False
        prefixes.append(prefix_object)

    return prefixes


def get_as_set_prefixes_list(as_set, ip_version):
    prefixes = get_as_set_prefixes(as_set, ip_version)
    prefixes_list = []
    for prefix in prefixes:
        prefixes_list.append(prefix['prefix'])
    return prefixes_list


def get_neighbor_installed_prefixes(device, afi_safi, remote_address):
    installedPrefixes = []
    filter_template = """
                <filter>
                  <bgp-state-data>
                    <bgp-route-vrfs>
                      <bgp-route-vrf>
                        <bgp-route-afs>
                          <bgp-route-af>
                           <afi-safi>{afi_safi}</afi-safi>
                            <bgp-route-neighbors>
                               <bgp-route-neighbor>
                                 <nbr-id>{neighbor}</nbr-id>
                                 <bgp-neighbor-route-filters/>
                               </bgp-route-neighbor>
                            </bgp-route-neighbors>
                          </bgp-route-af>
                        </bgp-route-afs>
                      </bgp-route-vrf>
                    </bgp-route-vrfs>
                  </bgp-state-data>
                </filter>"""

    netconf_payload = filter_template.format(afi_safi=afi_safi, neighbor=remote_address)
    reply = device.nc.get(filter=netconf_payload)
    data = xmltodict.parse(reply.data_xml)

    bgpRouteFilters = data['data']['bgp-state-data']['bgp-route-vrfs']['bgp-route-vrf']['bgp-route-afs']['bgp-route-af']['bgp-route-neighbors']['bgp-route-neighbor']['bgp-neighbor-route-filters']['bgp-neighbor-route-filter']

    if('bgp-neighbor-route-entries' in bgpRouteFilters):
        prefixes = bgpRouteFilters['bgp-neighbor-route-entries']['bgp-neighbor-route-entry']
        if(isinstance(prefixes, list)):
            for prefix in prefixes:
                installedPrefixes.append(prefix['prefix'])
        else:
            installedPrefixes.append(prefixes['prefix'])

    return installedPrefixes


def create_backup(device):
    rpc = rpcComponent()
    ckP = checkpointComponent()
    rpc.add(ckP)
    serializer = NETCONFVisitor()
    output = rpc.parse(serializer)
    backup_payload = serializer.print(output)

    checkpointReply = device.nc.request(backup_payload, timeout=40)
    checkpointStatus = xmltodict.parse(checkpointReply)
    if (checkpointStatus['rpc-reply']['result']['#text'] != 'Checkpoint successful'):
        raise Exception(f"Failed to backup on {device.name}\nRPC response: {checkpointReply}")


def get_backup_path(device):
    backupFilter = '''
    <filter>
        <checkpoint-archives>
        </checkpoint-archives>
    </filter>'''
    backupReply = device.nc.get(filter=backupFilter)
    backupData = xmltodict.parse(backupReply.data_xml)
    if backupData['data']['checkpoint-archives']['recent'] is not None:
        return backupData['data']['checkpoint-archives']['recent']
    else:
        raise Exeption("Failed to retrieve last backup")


def restore_device(device, backup_path):
    rpc = rpcComponent()
    roolback = rollbackComponent(target_url=backup_path)
    rpc.add(roolback)
    serializer = NETCONFVisitor()
    output = rpc.parse(serializer)
    rollbackPayload = serializer.print(output)

    reply = device.nc.request(rollbackPayload, timeout=40)
    rollbackData = xmltodict.parse(reply)
    if 'result' not in rollbackData['rpc-reply']:
        raise Exception(reply)
