---
title: About
description: >-
  Who writes the RadiusDeck Blog, how the FreeRADIUS guides are tested, and how
  to report a correction.
permalink: /about/
---

# About this blog

The RadiusDeck Blog publishes practical guides for administrators who connect
network devices, such as access points and VPN gateways, to FreeRADIUS. The articles are
written by the RadiusDeck team, the maintainers of
[RadiusDeck]({{ site.product_url }}), an open-source web interface for
managing FreeRADIUS clients in `clients.conf`.

## How the guides are tested

- Commands and configuration examples are run on an isolated test setup before
  publication. Each article lists the software versions and the date of the
  last technical check.
- Behavior that depends on a version, distribution, or deployment is labeled as
  such. Defaults can change between FreeRADIUS releases, so check them against
  your own installation.
- Addresses come from documentation ranges such as `192.0.2.0/24`, and device
  names and shared secrets are fictional. Replace them with your own values.
- Technical claims link to primary sources, such as FreeRADIUS configuration
  comments, manual pages, and project announcements.

When a guide is revised, it keeps its address and shows the date of the update.

## What RadiusDeck covers

RadiusDeck manages RADIUS clients: the network devices that send requests to
FreeRADIUS. End-user accounts, SQL, and authentication policies are configured
in FreeRADIUS itself. The guides say when a step is done in FreeRADIUS and when
RadiusDeck can help with it.

## Corrections

If a guide is wrong or outdated for your version, open an issue in the
[blog repository](https://github.com/radiusdeck/radiusdeck.github.io/issues).
Include the FreeRADIUS version and remove shared secrets, passwords, and
private addresses before posting.
