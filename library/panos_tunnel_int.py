#!/usr/bin/env python

#  Copyright 2016 Palo Alto Networks, Inc
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

DOCUMENTATION = '''
---
module: panos_interface
short_description: configure data-port network interface for DHCP
description:
    - Configure data-port (DP) network interface for DHCP. By default DP interfaces are static.
author: "Luigi Mori (@jtschichold), Ivan Bojer (@ivanbojer)"
version_added: "2.3"
requirements:
    - pan-python can be obtained from PyPI U(https://pypi.python.org/pypi/pan-python)
    - pandevice can be obtained from PyPI U(https://pypi.python.org/pypi/pandevice)
note:
    - Checkmode is not supported.
options:
    ip_address:
        description:
            - IP address (or hostname) of PAN-OS device being configured.
        required: true
    username:
        description:
            - Username credentials to use for auth.
        default: "admin"
    password:
        description:
            - Password credentials to use for auth.
    api_key:
        description:
            - API key that can be used instead of I(username)/I(password) credentials.
    operation:
        description:
            - The action to be taken.  Supported values are I(add)/I(update)/I(delete).
            - This is used only if "state" is unspecified.
        default: "add"
    state:
        description:
            - The state.  Can be either I(present)/I(absent).
            - If this is defined, then "operation" is ignored.
    if_name:
        description:
            - Name of the interface to configure.
        required: true
    mode:
        description:
            - The interface mode.
            - Supported values are I(layer3)/I(layer2)/I(virtual-wire)/I(tap)/I(ha)/I(decrypt-mirror)/I(aggregate-group)
        default: "layer3"
    ip:
        description:
            - List of static IP addresses.
    ipv6_enabled:
        description:
            - Enable IPv6.
    management_profile:
        description:
            - Interface management profile name.
    mtu:
        description:
            - MTU for layer3 interface.
    adjust_tcp_mss:
        description:
            - Adjust TCP MSS for layer3 interface.
    netflow_profile:
        description:
            - Netflow profile for layer3 interface.
    lldp_enabled:
        description:
            - Enable LLDP for layer2 interface.
    lldp_profile:
        description:
            - LLDP profile name for layer2 interface.
    netflow_profile_l2:
        description:
            - Netflow profile name for layer2 interface.
    link_speed:
        description:
            - Link speed.  Supported values are I(auto)/I(10)/I(100)/I(1000).
    link_duplex:
        description:
            - Link duplex.  Supported values are I(auto)/I(full)/I(half).
    link_state:
        description:
            - Link state.  Supported values are I(auto)/I(up)/I(down).
    aggregate_group:
        description:
            - Aggregate interface name.
    comment:
        description:
            - Interface comment.
    ipv4_mss_adjust:
        description:
            - (7.1+) TCP MSS adjustment for IPv4.
    ipv6_mss_adjust:
        description:
            - (7.1+) TCP MSS adjustment for IPv6.
    enable_dhcp:
        description:
            - Enable DHCP on this interface.
        default: "true"
    create_default_route:
        description:
            - Whether or not to add default route with router learned via DHCP.
        default: "false"
    dhcp_default_route_metric:
        description:
            - Metric for the DHCP default route.
    zone_name:
        description:
            - Name of the zone for the interface. If the zone does not exist it is created.
            - If the zone exists and it is not of the correct mode the operation will fail.
        required: true
    vr_name:
        description:
            - Name of the virtual router; it must already exist.
        default: "default"
    vsys_dg:
        description:
            - Name of the vsys (if firewall) or device group (if panorama) to put this object.
        default: "vsys1"
    commit:
        description:
            - Commit if changed
        default: true
'''

EXAMPLES = '''
# Create ethernet1/1 as DHCP.
- name: enable DHCP client on ethernet1/1 in zone public
  panos_tunnel_int:
    ip_address: "192.168.1.1"
    username: "ansible"
    password: "secret"
    if_name: "tunnel.1"
    zone_name: "public"
    enable_dhcp: true
    dhcp_default_route: "no"

# Update ethernet1/2 with a static IP address in zone dmz.
- name: ethernet1/2 as static in zone dmz
  panos_tunnel_int:
    ip_address: "192.168.1.1"
    username: "ansible"
    password: "secret"
    if_name: "tunnel.2"
    mode: "layer3"
    ip: ["10.1.1.1/24"]
    enable_dhcp: false
    zone_name: "dmz"
'''

RETURN = '''
# Default return values
'''

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.basic import get_exception


try:
    from pandevice.base import PanDevice
    from pandevice.network import EthernetInterface, Zone, VirtualRouter, TunnelInterface
    from pandevice.device import Vsys
    from pandevice.errors import PanDeviceError
    HAS_LIB = True
except ImportError:
    HAS_LIB = False


def set_zone(con, tun, zone_name, zones):
    changed = False
    desired_zone = None

    # Remove the interface from the zone.
    for z in zones:
        if z.name == zone_name:
            desired_zone = z
        elif tun.name in z.interface:
            z.interface.remove(tun.name)
            z.update('interface')
            changed = True

    if desired_zone is not None:
        if desired_zone.interface is None:
            desired_zone.interface = []
        if tun.name not in desired_zone.interface:
            desired_zone.interface.append(tun.name)
            desired_zone.update('interface')
            changed = True
    elif zone_name is not None:
        z = Zone(zone_name, interface=[tun.name])
        con.add(z)
        z.create()
        changed = True

    return changed


def set_virtual_router(con, tun, vr_name, routers):
    changed = False
    desired_vr = None

    for vr in routers:
        if vr.name == vr_name:
            desired_vr = vr

        elif vr.interface and tun.name in vr.interface:
            vr.interface.remove(tun.name)
            vr.update('interface')
            changed = True

    if desired_vr is not None:
        if desired_vr.interface is None:
            desired_vr.interface = []
        if tun.name not in desired_vr.interface:
            desired_vr.interface.append(tun.name)
            desired_vr.update('interface')
            changed = True
    elif vr_name is not None:
        raise ValueError('Virtual router {0} does not exist'.format(vr_name))

    return changed


def main():
    argument_spec = dict(
        ip_address=dict(required=True),
        password=dict(no_log=True),
        username=dict(default='admin'),
        api_key=dict(no_log=True),
        operation=dict(default='add', choices=['add', 'update', 'delete']),
        state=dict(choices=['present', 'absent']),
        if_name=dict(required=True),
        ip=dict(type='list'),
        ipv6_enabled=dict(),
        management_profile=dict(),
        mtu=dict(),
        netflow_profile=dict(),
        comment=dict(),
        zone_name=dict(required=True),
        vr_name=dict(default='default'),
        vsys_dg=dict(default='vsys1'),
        commit=dict(type='bool', default=True),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=False,
                           required_one_of=[['api_key', 'password']])
    if not HAS_LIB:
        module.fail_json(msg='Missing required libraries.')

    # Get the firewall / panorama auth.
    auth = [module.params[x] for x in
            ('ip_address', 'username', 'password', 'api_key')]

    # Get the object params.
    spec = {
        'name': module.params['if_name'],
        'ip': module.params['ip'],
        'ipv6_enabled': module.params['ipv6_enabled'],
        'management_profile': module.params['management_profile'],
        'mtu': module.params['mtu'],
        'netflow_profile': module.params['netflow_profile'],
        'comment': module.params['comment'],
    }

    # Get other info.
    operation = module.params['operation']
    state = module.params['state']
    zone_name = module.params['zone_name']
    vr_name = module.params['vr_name']
    vsys_dg = module.params['vsys_dg']
    commit = module.params['commit']
    if_name = module.params['if_name']

    # Open the connection to the PANOS device.
    con = PanDevice.create_from_device(*auth)

    # Set vsys if firewall, device group if panorama.
    if hasattr(con, 'refresh_devices'):
        # Panorama
        # Normally we want to set the device group here, but there are no
        # interfaces on Panorama.  So if we're given a Panorama device, then
        # error out.
        '''
        groups = panorama.DeviceGroup.refreshall(con, add=False)
        for parent in groups:
            if parent.name == vsys_dg:
                con.add(parent)
                break
        else:
            module.fail_json(msg="'{0}' device group is not present".format(vsys_dg))
        '''
        module.fail_json(msg="Ethernet interfaces don't exist on Panorama")
    else:
        # Firewall
        # Normally we should set the vsys here, but since interfaces are
        # vsys importables, we'll use organize_into_vsys() to help find and
        # cleanup when the interface is imported into an undesired vsys.
        # con.vsys = vsys_dg
        pass

    # Retrieve the current config.
    try:
        interfaces = TunnelInterface.refreshall(con, add=False, name_only=True)
        zones = Zone.refreshall(con)
        routers = VirtualRouter.refreshall(con)
        vsys_list = Vsys.refreshall(con)
    except PanDeviceError:
        e = get_exception()
        module.fail_json(msg=e.message)

    # Build the object based on the user spec.
    tun = TunnelInterface(**spec)
    con.add(tun)

    # Which action should we take on the interface?
    changed = False
    if state == 'present':
        if tun.name in [x.name for x in interfaces]:
            i = TunnelInterface(tun.name)
            con.add(i)
            try:
                i.refresh()
            except PanDeviceError as e:
                module.fail_json(msg='Failed "present" refresh: {0}'.format(e))
            if not i.equal(tun, compare_children=False):
                tun.extend(i.children)
                try:
                    tun.apply()
                    changed = True
                except PanDeviceError as e:
                    module.fail_json(msg='Failed "present" apply: {0}'.format(e))
        else:
            try:
                tun.create()
                changed = True
            except PanDeviceError as e:
                module.fail_json(msg='Failed "present" create: {0}'.format(e))
        try:
            changed |= set_zone(con, tun, zone_name, zones)
            changed |= set_virtual_router(con, tun, vr_name, routers)
        except PanDeviceError as e:
            module.fail_json(msg='Failed zone/vr assignment: {0}'.format(e))
    elif state == 'absent':
        try:
            changed |= set_zone(con, tun, None, zones)
            changed |= set_virtual_router(con, tun, None, routers)
        except PanDeviceError as e:
            module.fail_json(msg='Failed "absent" zone/vr cleanup: {0}'.format(e))
            changed = True
        if tun.name in [x.name for x in interfaces]:
            try:
                tun.delete()
                changed = True
            except PanDeviceError as e:
                module.fail_json(msg='Failed "absent" delete: {0}'.format(e))
    elif operation == 'delete':
        if tun.name not in [x.name for x in interfaces]:
            module.fail_json(msg='Interface {0} does not exist, and thus cannot be deleted'.format(tun.name))

        try:
            con.organize_into_vsys()
            set_zone(con, tun, None, zones)
            set_virtual_router(con, tun, None, routers)
            tun.delete()
            changed = True
        except (PanDeviceError, ValueError):
            e = get_exception()
            module.fail_json(msg=e.message)
    elif operation == 'add':
        if tun.name in [x.name for x in interfaces]:
            module.fail_json(msg='Interface {0} is already present; use operation "update"'.format(tun.name))

        con.vsys = vsys_dg
        # Create the interface.
        try:
            tun.create()
            set_zone(con, tun, zone_name, zones)
            set_virtual_router(con, tun, vr_name, routers)
            changed = True
        except (PanDeviceError, ValueError):
            e = get_exception()
            module.fail_json(msg=e.message)
    elif operation == 'update':
        if tun.name not in [x.name for x in interfaces]:
            module.fail_json(msg='Interface {0} is not present; use operation "add" to create it'.format(tun.name))

        # If the interface is in the wrong vsys, remove it from the old vsys.
        try:
            con.organize_into_vsys()
        except PanDeviceError:
            e = get_exception()
            module.fail_json(msg=e.message)
        if tun.vsys != vsys_dg:
            try:
                tun.delete_import()
            except PanDeviceError:
                e = get_exception()
                module.fail_json(msg=e.message)

        # Move the ethernet object to the correct vsys.
        for vsys in vsys_list:
            if vsys.name == vsys_dg:
                vsys.add(tun)
                break
        else:
            module.fail_json(msg='Vsys {0} does not exist'.format(vsys))

        # Update the interface.
        try:
            tun.apply()
            set_zone(con, tun, zone_name, zones)
            set_virtual_router(con, tun, vr_name, routers)
            changed = True
        except (PanDeviceError, ValueError):
            e = get_exception()
            module.fail_json(msg=e.message)
    else:
        module.fail_json(msg="Unsupported operation '{0}'".format(operation))

    # Commit if we were asked to do so.
    if changed and commit:
        try:
            con.commit(sync=True)
        except PanDeviceError:
            e = get_exception()
            module.fail_json(msg='Performed {0} but commit failed: {1}'.format(operation, e.message))

    # Done!
    module.exit_json(changed=changed, msg='okey dokey')


if __name__ == '__main__':
    main()
