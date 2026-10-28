---
title: "FreeRADIUS clients.conf: Examples and Best Practices"
description: >-
  How to add RADIUS clients to FreeRADIUS clients.conf: minimal and subnet
  examples, shared secrets, Message-Authenticator, applying changes, testing
  with radtest, and fixing common errors.
tested:
  date: 2026-10-23
  environment: Official FreeRADIUS Docker image; paths also checked on the Ubuntu 24.04 package
  freeradius: "3.2.10 (Ubuntu 24.04 package: 3.2.5)"
  radiusdeck: "0.1.0"
related:
  - /blog/freeradius-unknown-client/
  - /blog/freeradius-web-gui/
---

**Short answer:** each device that sends requests to FreeRADIUS, such as an
access point, needs a `client` block in `clients.conf`
with the source IP address the server sees and a shared secret. The same secret
must be configured on the device. Check the configuration with
`freeradius -XC`, restart FreeRADIUS, then send a test request from that
address. FreeRADIUS 3 reads static clients only at startup, so a reload or HUP
signal does not add them.

* TOC
{:toc}

## Tested with

- FreeRADIUS 3.2.10, official Docker image `freeradius/freeradius-server:3.2.10`.
- File locations and the configuration check were also tested on the Ubuntu
  24.04 package, FreeRADIUS 3.2.5. The `systemctl` commands follow the package's
  systemd unit file; the restart itself was tested with Docker.
- Last technical check: October 23, 2026.

Addresses in this guide come from documentation ranges (`192.0.2.0/24`,
`203.0.113.0/24`). Replace them, and every secret, with your own values. In
the examples, the FreeRADIUS server is `192.0.2.1`, the access point
`office-ap-01` is `192.0.2.10`, and the other office devices are in
`192.0.2.0/24`.

## What counts as a RADIUS client

In FreeRADIUS terms, a *client* is the network device (NAS) that sends RADIUS
requests, for example an access point or a VPN gateway. The people who log in
through that device are users, and they are configured elsewhere, for example
in `mods-config/files/authorize` or an SQL database.

`clients.conf` answers one question: which devices may talk to this server, and
which shared secret each of them uses. Requests from an address that matches no
client are ignored. The log message is shown under
[Unknown client](#unknown-client); causes and fixes are in
[How to Fix FreeRADIUS Unknown Client Errors](/blog/freeradius-unknown-client/).

## Minimal client example

```text
client office-ap-01 {
	ipaddr = 192.0.2.10
	secret = "REPLACE-WITH-A-32-CHARACTER-RANDOM-SECRET"
}
```

- `office-ap-01` is the client name. It appears in log messages such as
  `(from client office-ap-01)`, so use a name that identifies the device.
- `ipaddr` is the source IP address of the requests as FreeRADIUS sees it.
  Behind NAT or Docker port publishing, this can differ from the address
  configured on the device.
- `secret` is the shared secret. The device must use exactly the same value.

You do not need `shortname`: the comments in the stock `clients.conf` describe
it as accepted for compatibility with version 1.x and no longer necessary since
2.0. `nas_type` is optional; the stock file explains that it is used by
`checkrad.pl` for simultaneous-use checks.

### Generate the shared secret

The stock `clients.conf` in FreeRADIUS 3.2.10 recommends a random secret of at
least 16 characters, preferably 32, and suggests this command:

```bash
dd if=/dev/random bs=1 count=24 | base64
```

It prints 32 characters. Keep the secret in double quotes in `clients.conf`.
FreeRADIUS warns at startup when a secret is short, for example for the
default test client:

```text
Shared secret for client localhost is short, and likely can be broken by an attacker.
```

### Prefer IP addresses to host names

`ipaddr` also accepts a DNS name, but the stock comments strongly recommend IP
addresses. The name is resolved once at startup, later DNS changes are not
seen, and the server does not start if the lookup fails.

## Several clients and whole networks

You can define one client per device, or one client for a network written in
CIDR notation:

```text
client office-ap-01 {
	ipaddr = 192.0.2.10
	secret = "REPLACE-WITH-SECRET-FOR-OFFICE-AP-01"
}

client office-network {
	ipaddr = 192.0.2.0/24
	secret = "REPLACE-WITH-SECRET-FOR-OFFICE-DEVICES"
}
```

`192.0.2.10` matches both entries. When a request arrives, FreeRADIUS uses the
most specific matching client, so requests from `192.0.2.10` use
`office-ap-01`. In our test, the access point was accepted only with its own
secret, and a request from it with the network secret got no reply. Other
addresses in the network, such as `192.0.2.23`, used the network secret.

Two `client` blocks with the same address are an error, and the server does not
start:

```text
Failed to add duplicate client dup-b
/etc/freeradius/clients.conf[408]: Failed to add client dup-b
```

A network entry is convenient, but every device in that range shares one
secret. Separate entries let you rotate the secret of one device without
touching the others.

## Find the clients.conf your server actually loads

Edit the file that the running server reads. The location depends on how
FreeRADIUS was installed:

| Installation | File |
|---|---|
| Ubuntu 24.04 package (`freeradius` 3.2.5) | `/etc/freeradius/3.0/clients.conf` |
| Official Docker image 3.2.10 | `/etc/freeradius/clients.conf` (`/etc/raddb` is a symlink to `/etc/freeradius`) |

To confirm, run the FreeRADIUS configuration check and look for the included
files:

```bash
sudo freeradius -XC | grep 'including configuration file'
```

```text
including configuration file /etc/freeradius/3.0/clients.conf
```

### Keep clients in separate files

`clients.conf` can include a directory:

```text
$INCLUDE clients.d/
```

Each file in `clients.d/` then holds one or more `client` blocks. The output
of `freeradius -XC` lists them:

```text
including files in directory /etc/freeradius/clients.d/
including configuration file /etc/freeradius/clients.d/branch-switch-01.conf
```

In our test, an editor backup file (`branch-switch-01.conf~`) in the same
directory was not loaded.

## Apply a change: save, check, restart, test

Each step can succeed while the next one fails, so check them separately.

### 1. Save the file

Make the change and save `clients.conf`.

If FreeRADIUS runs in Docker with `clients.conf` mounted as a single file,
edit the file in place. Tools that replace the file, such as `sed -i`, create a
new file on the host. The container keeps seeing the old one until it is
restarted. Mounting the whole configuration directory avoids this.

### 2. Check the configuration

```bash
# Package installation
sudo freeradius -XC

# Docker
docker exec <freeradius-container> freeradius -XC
```

Expected last line:

```text
Configuration appears to be OK
```

Do not skip this step. FreeRADIUS does not start with a broken configuration.
In our Docker test, restarting with a syntax error stopped the server instead
of leaving it running with the old configuration. The Ubuntu systemd unit also
runs a configuration check before it starts the server.

### 3. Restart FreeRADIUS

```bash
# Package installation (systemd)
sudo systemctl restart freeradius

# Docker
docker restart <freeradius-container>
```

Static clients are read at startup, so use `systemctl restart` after adding or
changing them. On the Ubuntu package, `systemctl reload freeradius` only checks
the configuration and sends the server a HUP signal. FreeRADIUS lead developer
Alan DeKok:
["You can't reload clients.conf via a HUP."](https://lists.freeradius.org/pipermail/freeradius-users/2021-July/100451.html)
If you need to add clients without restarting, look at FreeRADIUS dynamic
clients instead.

### 4. Send a test request

`radtest` is in the `freeradius-utils` package and in the official Docker
image. The request must come from the address in `ipaddr`. Run it on a Linux
host at that address, or temporarily add your test host as a client. Use a test
user that exists on your server:

```bash
radtest test-user test-password 192.0.2.1 0 'REPLACE-WITH-THE-CLIENT-SECRET'
```

Arguments: user name, password, server address, NAS port (`0`), and the shared
secret. Expected result:

```text
Received Access-Accept from 192.0.2.1:1812 to 192.0.2.10:<port> length 38
```

Read the result carefully:

- **`Access-Accept`**: the client is known, the secret matches, and the user
  authenticated.
- **`Access-Reject`**: the client entry works; the problem is the user's
  credentials or the authentication policy.
- **No reply**: the request was ignored or dropped. Check the server log and
  compare it with the messages under [Common errors](#common-errors).

## Message-Authenticator and BlastRADIUS settings

FreeRADIUS 3.2.10 drops requests without a Message-Authenticator attribute by
default, while the Ubuntu 24.04 package (3.2.5) accepts them by default.

Two settings control this: `require_message_authenticator` and
`limit_proxy_state`. Releases with the fix for the
[BlastRADIUS vulnerability](https://www.freeradius.org/vul_notifications/2024/07/09/blastradius.html)
(3.2.5 and 3.0.27 or later) set global defaults for both in the `security`
section of `radiusd.conf`, and a `client` block can override them. Defaults in
the versions we checked:

| Setting | 3.2.10, official image | 3.2.5, Ubuntu 24.04 |
|---|---|---|
| `require_message_authenticator` | `yes` | `auto` |
| `limit_proxy_state` | `auto` | `auto` |

Check your own `radiusd.conf`: the default of `require_message_authenticator`
changed between these versions.

A device that does not send Message-Authenticator gets no reply on 3.2.10
with default settings, and the log shows:

```text
Receive - Insecure packet from host 192.0.2.10:  Packet does not contain required Message-Authenticator attribute.  You may need to set "require_message_authenticator = no" in the configuration.
```

Recommendations:

- Update devices so they send Message-Authenticator, and keep
  `require_message_authenticator = yes`. The FreeRADIUS configuration comments
  call this the best protection against the attack.
- If a regular NAS cannot be updated yet, relax the check only in that
  device's `client` block, never globally. Set `limit_proxy_state = yes` in
  the same block:

  ```text
  client office-ap-01 {
  	ipaddr = 192.0.2.10
  	secret = "REPLACE-WITH-SECRET-FOR-OFFICE-AP-01"
  	require_message_authenticator = no
  	limit_proxy_state = yes
  }
  ```

  According to the configuration comments, most regular NASes do not add
  Proxy-State to the requests they originate. In our 3.2.10 test, this client got `Access-Accept` for requests without
  Message-Authenticator. Requests that also carried Proxy-State were dropped:

  ```text
  Receive - Insecure packet from host 192.0.2.10:  Packet does not contain required Message-Authenticator attribute, but still has one or more Proxy-State attributes
  ```

- Do not leave `limit_proxy_state` at `auto` for such a client. With
  `require_message_authenticator = no` and `auto`, the first request after a
  restart decides. In our test, a first request with Proxy-State and without
  Message-Authenticator switched the client to `false`. After that, such
  requests were accepted, which leaves neither protection in place:

  ```text
  Setting "limit_proxy_state = false" for client office-ap-01
  UPGRADE CLIENT office-ap-01 AS YOUR NETWORK IS VULNERABLE TO THE BLASTRADIUS ATTACK.
  ```

- Proxies and some wireless LAN controllers forward requests for other devices
  and add Proxy-State. With `limit_proxy_state = yes`, their requests without
  Message-Authenticator are dropped. Setting both options to `no` makes them
  work, but the FreeRADIUS configuration comments warn that at least one of the
  two must be `yes` for any protection against the attack. For these devices,
  the fix is an upgrade that makes them send Message-Authenticator, followed by
  `require_message_authenticator = yes`.
- For `require_message_authenticator`, the configuration comments add that
  `auto` has no effect for a client defined as a network (IP/mask).

## Common errors

### Wrong shared secret

The device gets no reply. FreeRADIUS 3.2.10 logs:

```text
Dropping packet without response because of error: Received packet from 192.0.2.10 with invalid Message-Authenticator!  (Shared secret is incorrect.) (from client office-ap-01)
```

The client was found (`from client office-ap-01`), so the address is right.
Compare the secret on the device and in `clients.conf` character by character.
A more specific client entry for the same address takes precedence; see
[Several clients and whole networks](#several-clients-and-whole-networks).

### Missing closing brace

```text
/etc/freeradius/clients.conf[414]: EOF reached without closing brace for section client starting at line 410
Errors reading or parsing /etc/freeradius/radiusd.conf
```

### Missing equals sign

`ipaddr 192.0.2.10` instead of `ipaddr = 192.0.2.10`:

```text
/etc/freeradius/clients.conf[406]: Expecting section start brace '{' after "ipaddr 192.0.2.10"
Errors reading or parsing /etc/freeradius/radiusd.conf
```

The number in brackets is the line in `clients.conf`.

### Unknown client

```text
Ignoring request to auth address * port 1812 bound to server default from unknown client 203.0.113.77 port 52631 proto udp
```

No client matches the source address of the request. Compare the address in
the message with the `ipaddr` values in the loaded `clients.conf`; `ipaddr` must
match the address in the message. Behind NAT or Docker port publishing, that
address can differ from the device's own. In our Docker test, a request sent
from the host to the published port `127.0.0.1:18121` arrived from the Docker
network gateway `10.88.10.1`; the result depends on the Docker network
configuration. If the client is already in the file, restart FreeRADIUS: a
client added after startup is not loaded yet.

For the other causes and how to confirm the fix, see
[How to Fix FreeRADIUS Unknown Client Errors](/blog/freeradius-unknown-client/).

## Frequently asked questions

### Do I need to restart FreeRADIUS after editing clients.conf?

Yes. FreeRADIUS 3 reads static clients at startup. `systemctl reload` sends a
HUP signal, and HUP does not reload `clients.conf`. Check the configuration
with `freeradius -XC` first, because the server does not start with an error in
the file.

### Where is clients.conf?

On the Ubuntu 24.04 package it is `/etc/freeradius/3.0/clients.conf`. In the
official Docker image 3.2.10 it is `/etc/freeradius/clients.conf`. The output
of `freeradius -XC` lists the file the server loads.

### Can one client entry cover a whole subnet?

Yes. Set `ipaddr` to a CIDR range such as `192.0.2.0/24`. When an address also
has its own client entry, FreeRADIUS uses the most specific match.

### Can I use a hostname in ipaddr?

FreeRADIUS accepts a DNS name, but resolves it once at startup and does not
start if the lookup fails. The comments in the stock configuration recommend IP
addresses.

### How long should a shared secret be?

The FreeRADIUS 3.2.10 configuration comments recommend at least 16 random
characters, preferably 32. `dd if=/dev/random bs=1 count=24 | base64` prints a
32-character secret.

### Why does FreeRADIUS not answer my device?

When a request gets no reply, the server log usually shows why. The common
messages are an unknown client, an invalid Message-Authenticator from a wrong shared
secret, and a packet without a required Message-Authenticator attribute. Each
is shown under [Common errors](#common-errors) and
[Message-Authenticator and BlastRADIUS settings](#message-authenticator-and-blastradius-settings).

## Manage clients.conf from a web interface

Editing `clients.conf` by hand works well for a few devices. If you manage
many devices and rotate their secrets, you can use
[RadiusDeck](https://github.com/radiusdeck/radiusdeck). This open-source web
interface edits the `clients.conf` file you point it to. It preserves
comments, blank lines, order, and nested blocks, and creates a backup before
each change. You still apply changes by restarting FreeRADIUS, or through an
optional reload sidecar. RadiusDeck manages clients only; user accounts and
authentication policies stay in FreeRADIUS.

[FreeRADIUS Web GUI: How to Manage RADIUS Clients](/blog/freeradius-web-gui/)
shows the setup step by step: running RadiusDeck next to FreeRADIUS, adding
and editing a client, applying the change, and testing it with `radtest`.

## Sources

- Comments in the stock `clients.conf` and `radiusd.conf` of FreeRADIUS 3.2.10.
- [radmin(8), FreeRADIUS 3.2.10](https://github.com/FreeRADIUS/freeradius-server/blob/release_3_2_10/man/man8/radmin.8).
- [BlastRADIUS Vulnerability](https://www.freeradius.org/vul_notifications/2024/07/09/blastradius.html), FreeRADIUS project.
- [Reload Freeradius server without Restart](https://lists.freeradius.org/pipermail/freeradius-users/2021-July/100451.html), freeradius-users mailing list, July 2021.
