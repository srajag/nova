# Copyright 2016 Red Hat, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

'''
This module contains code for converting from the original
nova.network.model data structure, to the new os-vif based
versioned object model os_vif.objects.*
'''

import sys

import os_vif
from os_vif import objects
from oslo_config import cfg
from oslo_log import log as logging

from nova import exception
from nova.network import model


LOG = logging.getLogger(__name__)
CONF = cfg.CONF

os_vif.initialize()


def _get_vif_name(vif):
    if vif.get('devname', None) is not None:
        return vif['devname']
    return ('nic' + vif['id'])[:model.NIC_NAME_LEN]


def _get_hybrid_bridge_name(vif):
    return ('qbr' + vif['id'])[:model.NIC_NAME_LEN]


def _get_firewall_required(vif):
    if vif.is_neutron_filtering_enabled():
        return False
    if CONF.firewall_driver != "nova.virt.firewall.NoopFirewallDriver":
        return True
    return False


def convert_instance(instance):
    info = objects.instance_info.InstanceInfo(
        uuid=instance.uuid,
        name=instance.name)

    if (instance.obj_attr_is_set("project_id") and
            instance.project_id is not None):
        info.project_id = instance.project_id

    return info


def _convert_ip(ip):

    floating_ips = [fip['address'] for fip in ip.get('floating_ips', [])]
    return objects.fixed_ip.FixedIP(
        address=ip['address'],
        floating_ips=floating_ips)


def _convert_ips(ips):
    return objects.fixed_ip.FixedIPList(
        objects=[_convert_ip(ip) for ip in ips])


def _convert_route(route):
    """Convert Nova route object into os_vif object

    :param route: nova.network.model.Route instance

    :returns: os_vif.objects.route.Route instance
    """

    return objects.route.Route(
        cidr=route['cidr'],
        gateway=route['gateway']['address'],
        interface=route['interface'])


def _convert_routes(routes):
    """Convert Nova route list into os_vif object

    :param routes: list of nova.network.model.Route instances

    :returns: os_vif.objects.route.RouteList instance
    """

    return objects.route.RouteList(
        objects=[_convert_route(route) for route in routes])


def _convert_subnet(subnet):
    """Convert Nova subnet object into os_vif object

    :param subnet: nova.network.model.Subnet instance

    :returns: os_vif.objects.subnet.Subnet instance
    """

    dnsaddrs = [ip['address'] for ip in subnet['dns']]

    obj = objects.subnet.Subnet(
        dns=dnsaddrs,
        ips=_convert_ips(subnet['ips']),
        routes=_convert_routes(subnet['routes']))
    if subnet['cidr'] is not None:
        obj.cidr = subnet['cidr']
    if subnet['gateway']['address'] is not None:
        obj.gateway = subnet['gateway']['address']
    return obj


def _convert_subnets(subnets):
    """Convert Nova subnet list into os_vif object

    :param subnets: list of nova.network.model.Subnet instances

    :returns: os_vif.objects.subnet.SubnetList instance
    """

    return objects.subnet.SubnetList(
        objects=[_convert_subnet(subnet) for subnet in subnets])


def _convert_network(network):
    """Convert Nova network object into os_vif object

    :param network: nova.network.model.Network instance

    :returns: os_vif.objects.network.Network instance
    """

    netobj = objects.network.Network(
        id=network['id'],
        subnets=_convert_subnets(network['subnets']))
    if network["bridge"] is not None:
        netobj.bridge = network['bridge']
    if network['label'] is not None:
        netobj.label = network['label']

    return netobj


def _get_vif_instance(vif, cls, **kwargs):
    return cls(
        id=vif['id'],
        address=vif['address'],
        network=_convert_network(vif['network']),
        has_traffic_filtering=vif.is_neutron_filtering_enabled(),
        **kwargs)


# VIF_TYPE_BRIDGE = 'bridge'
def _convert_vif_bridge(vif):
    obj = _get_vif_instance(
        vif,
        objects.vif.VIFBridge,
        plugin="linux_bridge",
        vif_name=_get_vif_name(vif))
    if vif["network"]["bridge"] is not None:
        obj.bridge_name = vif["network"]["bridge"]
    return obj


# VIF_TYPE_OVS = 'ovs'
def _convert_vif_ovs(vif):
    profile = objects.vif.VIFPortProfileOpenVSwitch(
        interface_id=vif.get('ovs_interfaceid') or vif['id'])
    if _get_firewall_required(vif) or vif.is_hybrid_plug_enabled():
        obj = _get_vif_instance(
            vif,
            objects.vif.VIFBridge,
            port_profile=profile,
            plugin="ovs",
            vif_name=_get_vif_name(vif),
            bridge_name=_get_hybrid_bridge_name(vif))
    else:
        obj = _get_vif_instance(
            vif,
            objects.vif.VIFOpenVSwitch,
            port_profile=profile,
            plugin="ovs",
            vif_name=_get_vif_name(vif))
        if vif["network"]["bridge"] is not None:
            obj.bridge_name = vif["network"]["bridge"]
    return obj


# VIF_TYPE_IVS = 'ivs'
def _convert_vif_ivs(vif):
    raise NotImplementedError()


# VIF_TYPE_DVS = 'dvs'
def _convert_vif_dvs(vif):
    raise NotImplementedError()


# VIF_TYPE_IOVISOR = 'iovisor'
def _convert_vif_iovisor(vif):
    raise NotImplementedError()


# VIF_TYPE_802_QBG = '802.1qbg'
def _convert_vif_802_1qbg(vif):
    raise NotImplementedError()


# VIF_TYPE_802_QBH = '802.1qbh'
def _convert_vif_802_1qbh(vif):
    raise NotImplementedError()


# VIF_TYPE_HW_VEB = 'hw_veb'
def _convert_vif_hw_veb(vif):
    raise NotImplementedError()


# VIF_TYPE_IB_HOSTDEV = 'ib_hostdev'
def _convert_vif_ib_hostdev(vif):
    raise NotImplementedError()


# VIF_TYPE_MIDONET = 'midonet'
def _convert_vif_midonet(vif):
    raise NotImplementedError()


# VIF_TYPE_VHOSTUSER = 'vhostuser'
def _convert_vif_vhostuser(vif):
    profile = objects.vif.VIFPortProfileOpenVSwitch(
        interface_id=vif.get('ovs_interfaceid') or vif['id'])
    if vif['details'].get(model.VIF_DETAILS_VHOSTUSER_OVS_PLUG, False):
        obj = _get_vif_instance(vif, objects.vif.VIFVHostUser,
                                port_profile=profile, plugin="ovs",
                                vif_name=_get_vif_name(vif))
        if vif["network"]["bridge"] is not None:
            obj.bridge_name = vif["network"]["bridge"]
        obj.mode = vif['details'].get(
            model.VIF_DETAILS_VHOSTUSER_MODE, 'client')
        obj.path = vif['details'].get(
            model.VIF_DETAILS_VHOSTUSER_SOCKET)
        obj.has_traffic_filtering = vif.is_neutron_filtering_enabled()
        if obj.path is None:
            raise exception.VifDetailsMissingVhostuserSockPath(
                vif_id=vif['id'])
        return obj
    else:
        raise NotImplementedError()


# VIF_TYPE_VROUTER = 'vrouter'
def _convert_vif_vrouter(vif):
    raise NotImplementedError()


# VIF_TYPE_TAP = 'tap'
def _convert_vif_tap(vif):
    raise NotImplementedError()


# VIF_TYPE_MACVTAP = 'macvtap'
def _convert_vif_macvtap(vif):
    raise NotImplementedError()


# VIF_TYPE_HOSTDEV = 'hostdev_physical'
def _convert_vif_hostdev_physical(vif):
    raise NotImplementedError()


def convert_vif(vif):
    """Convert a Nova VIF model to an OS-VIF object

    :param vif: a nova.network.model.VIF instance

    :returns: a os_vif.objects.vif.VIFBase subclass
    """

    LOG.debug("Converting VIF %s", str(vif))

    funcname = "_convert_vif_" + vif['type'].replace(".", "_")
    func = getattr(sys.modules[__name__], funcname, None)

    if not func:
        raise exception.NovaException(
            "Unsupported VIF type %(type)s convert '%(func)s'" %
            {'type': vif['type'], 'func': funcname})

    try:
        vifobj = func(vif)
        LOG.debug("Converted object %s", str(vifobj))
        return vifobj
    except NotImplementedError:
        LOG.debug("No conversion for VIF type %s yet",
                  vif['type'])
        return None
