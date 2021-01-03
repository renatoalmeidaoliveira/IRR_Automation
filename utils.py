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
from xml.dom.minidom import parseString

import xmltodict
import requests
import json
import logging
import subprocess


def createBackup(device):
    rpc = rpcComponent()
    ckP = checkpointComponent()
    rpc.add(ckP)
    serializer = NETCONFVisitor()
    output = rpc.parse(serializer)
    xml_string = serializer.print(output)
    checkpointReply = device.nc.request(xml_string, timeout=40)
    checkpointStatus = xmltodict.parse(checkpointReply)
    if (checkpointStatus['rpc-reply']['result']['#text'] != 'Checkpoint successful'):
        raise Exception(f"Failed to backup on {device.name}\nRPC response: {checkpointReply}")


def getLastBackup(device):
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


def rollbackDevice(device, path):
    rpc = rpcComponent()
    roolback = rollbackComponent(target_url=path)
    rpc.add(roolback)
    serializer = NETCONFVisitor()
    output = rpc.parse(serializer)
    xml_string = serializer.print(output)
    reply = device.nc.request(xml_string, timeout=40)
    return reply


def getASSet(asn):
    request = requests.get(
            "https://www.peeringdb.com/api/net?asn=" + str(asn))
    request.raise_for_status()
    response = json.loads(request.text)
    return response['data'][0]['irr_as_set']


def getASPrefixes(as_set, ip_version, aggregate=None,):
    args = ["bgpq4", "-j"]
    if(ip_version == 4 or ip_version == 6):
        args.append("-" + str(ip_version))
    else:
        raise Exeption("Incorrect IP version")
    if(aggregate):
        args.append("-A")
    args.append("-lirr_prefix")
    args.append(as_set)
    process = subprocess.run(args, stdout=subprocess.PIPE)
    output = json.loads(process.stdout)
    return output['irr_prefix']


def createPrefixListPayload(name, prefixes):
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


def getConfiguredPrefixesFilter(asn):
    filter_component = filterComponent()
    native_component = nativeComponent()
    ip_component = ipComponent()
    as_set = getASSet(asn=asn)
    helper = ConfigurePrefixList(name=as_set)
    prefix_list_component = helper.getPrefixList()
    filter_component.add(native_component)
    native_component.add(ip_component)
    ip_component.add(prefix_list_component)
    serializer = NETCONFVisitor()
    output = filter_component.parse(serializer)
    xml_string = serializer.print(output)
    return xml_string

