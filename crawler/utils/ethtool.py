
import array
import fcntl
import socket
import struct

SIOCETHTOOL = 0x8946

ETHTOOL_GSET = 0x00000001
ETHTOOL_GSTRINGS = 0x0000001b
ETHTOOL_GSTATS = 0x0000001d
ETHTOOL_GSSET_INFO = 0x00000037

ETH_SS_STATS = 1


def stripped(name):
    return "".join(i for i in name if 31 < ord(i) < 127)


def ethtool_get_stats(nic):
    sockfd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    ecmd_sset_info = array.array('B', struct.pack('@IIQI',
                                                  ETHTOOL_GSSET_INFO,
                                                  0,
                                                  1 << ETH_SS_STATS,
                                                  0))
    ifreq = struct.pack('@16sP16x', nic, ecmd_sset_info.buffer_info()[0])
    try:
        fcntl.ioctl(sockfd, SIOCETHTOOL, ifreq)
    except IOError as err:
        raise err
    res = ecmd_sset_info.tostring()
    _, _, _, n_stats = struct.unpack('IIQI', res)

    if not n_stats:
        return {}

    ecmd_gstrings = array.array('B', struct.pack('@III%ds' % (n_stats * 32),
                                                 ETHTOOL_GSTRINGS,
                                                 ETH_SS_STATS,
                                                 0,
                                                 '\x00' * 32 * n_stats))
    ifreq = struct.pack('@16sP16x', nic, ecmd_gstrings.buffer_info()[0])
    try:
        fcntl.ioctl(sockfd, SIOCETHTOOL, ifreq)
    except IOError as err:
        raise err

    gstrings = ecmd_gstrings.tostring()
    name = gstrings[12:32].strip()

    # Get the peer ifindex number
    ecmd_gstats = array.array('B', struct.pack('@II%ds' % (n_stats * 8),
                                               ETHTOOL_GSTATS,
                                               ETH_SS_STATS,
                                               '\x00' * 8 * n_stats))
    ifreq = struct.pack('@16sP16x', nic, ecmd_gstats.buffer_info()[0])
    try:
        fcntl.ioctl(sockfd, SIOCETHTOOL, ifreq)
    except IOError as err:
        raise err

    gstats = ecmd_gstats.tostring()

    res = {}
    gstrings_idx = 12
    gstats_idx = 8

    while n_stats > 0:
        name = stripped(gstrings[gstrings_idx:gstrings_idx + 32])
        gstrings_idx += 32
        value, = struct.unpack('@Q', gstats[gstats_idx:gstats_idx + 8])
        gstats_idx += 8
        res[name] = value
        n_stats -= 1

    return res


def ethtool_get_peer_ifindex(nic):
    """
      Get the interface index of the peer device of a veth device.
      Returns a positive number in case the peer device's interface
      index could be determined, a negative value otherwise.
    """
    try:
        res = ethtool_get_stats(nic)
        return int(res.get('peer_ifindex', -1))
    except:
        return -2
