---
title: How to Fix FreeRADIUS Unknown Client Errors
description: >-
  Fix "Ignoring request ... from unknown client" in FreeRADIUS: read the source
  address from the log, check NAT and Docker, find the clients.conf the server
  loads, restart, and confirm the fix with radtest.
tested:
  date: 2026-10-26
  environment: Official FreeRADIUS Docker image, Docker 29.9.2
  freeradius: "3.2.10"
related:
  - /blog/freeradius-clients-conf/
  - /blog/freeradius-web-gui/
---

**Short answer:** `Ignoring request ... from unknown client 192.0.2.10` means
that no client entry in the configuration FreeRADIUS loaded matches the source
IP address of the request, so the server drops it without a reply. Take the
address from the message, add or fix a `client` block with that address in the
`clients.conf` the server actually reads, check the configuration with
`freeradius -XC`, restart FreeRADIUS, and send the request again. The shared
secret and the `NAS-IP-Address` attribute play no part in this check.

* TOC
{:toc}

## Tested with

- FreeRADIUS 3.2.10, official Docker image `freeradius/freeradius-server:3.2.10`,
  on Docker 29.9.2.
- Log file location checked on the Ubuntu 24.04 package, FreeRADIUS 3.2.5.
- Last technical check: October 26, 2026.

Addresses come from documentation ranges (`192.0.2.0/24`, `2001:db8::/32`). In
the examples, the FreeRADIUS server is `192.0.2.1`, and the access points
`office-ap-01` and `office-ap-02` are `192.0.2.10` and `192.0.2.11`. The Docker
gateway addresses `10.88.10.1` and `172.17.0.1` are the real addresses from our
test setup. Replace all addresses and secrets with your own.

## The error message

With FreeRADIUS in debug mode (`freeradius -X`), the message looks like this:

```text
Ignoring request to auth address * port 1812 bound to server default from unknown client 192.0.2.10 port 47823 proto udp
```

When the server runs normally, the same line goes to the log file with an
`Error:` prefix. On the Ubuntu package the file is
`/var/log/freeradius/radius.log`:

```text
Mon Oct 26 06:17:36 2026 : Error: Ignoring request to auth address * port 1812 bound to server default from unknown client 192.0.2.10 port 40926 proto udp
```

Each part of the message points to something you can check:

- `auth address * port 1812`: the socket that received the request. `auth` is
  for authentication, `acct` for accounting (port `1813`).
- `bound to server default`: the virtual server of that socket.
- `unknown client 192.0.2.10`: the source IP address of the request, as
  FreeRADIUS sees it.
- `port 47823 proto udp`: the source port. It can change between requests and
  plays no part in selecting the client entry.

FreeRADIUS does not answer an unknown client, so the device sees a timeout.
`radtest` sends the request three times and gives up:

```text
(0) No reply from server for ID 132 socket 3
```

Accounting requests from the same device produce the same error for the
`acct` socket:

```text
Ignoring request to acct address * port 1813 bound to server default from unknown client 192.0.2.10 port 50595 proto udp
```

## Find the cause

Compare the address in the message with the `ipaddr` values of your clients.
The table lists the causes we reproduced, in the order worth checking:

| Cause | How to recognize it |
|---|---|
| [No client for this address](#no-client-for-this-address) | No `client` block has this `ipaddr`, and no network entry contains it |
| [The address is not what you expected](#the-source-address-is-not-what-you-expected) | The message shows a NAT, Docker gateway, or IPv6 address |
| [The client is in a file the server does not load](#the-client-is-in-a-file-the-server-does-not-load) | `freeradius -XC` does not list the file with the client |
| [The change was not applied](#the-change-has-not-been-applied) | The client is in the loaded file, but the server was not restarted |
| [The client belongs to another virtual server](#the-client-belongs-to-another-virtual-server) | The client is inside a `server` section, and the message names a different server or port |

### No client for this address

Add a client with the address from the message:

```text
client office-ap-01 {
	ipaddr = 192.0.2.10
	secret = "REPLACE-WITH-A-32-CHARACTER-RANDOM-SECRET"
}
```

The [clients.conf guide](/blog/freeradius-clients-conf/) explains the fields,
how to generate the secret, and how one entry can cover a whole network.

### The source address is not what you expected

FreeRADIUS selects the client by the source IP address of the packet. The
attributes inside the request do not matter. In our test, a request from
`192.0.2.11` carried `NAS-IP-Address = 192.0.2.10`, the address of a configured
client, and was still ignored:

```text
Ignoring request to auth address * port 1812 bound to server default from unknown client 192.0.2.11 port 40370 proto udp
```

The source address can differ from the one you configured for the device:

- **NAT.** Behind NAT, FreeRADIUS sees the translated address. The same applies
  when a device sends requests from a different interface than the one you
  expect, for example its management address instead of its LAN address.
  Either configure the device to send from the expected address, or use the
  address from the message.
- **Docker port publishing.** In our tests, requests sent to a published port
  arrived from the address of the Docker network gateway, not from the sender.
  A request from the Docker host to `127.0.0.1:18121` arrived from `10.88.10.1`,
  the gateway of the container's network. A request from a container in another
  Docker network to the host address arrived from `172.17.0.1`, the gateway of
  the default `bridge` network:

  ```text
  Ignoring request to auth address * port 1812 bound to server default from unknown client 10.88.10.1 port 59933 proto udp
  Ignoring request to auth address * port 1812 bound to server default from unknown client 172.17.0.1 port 59601 proto udp
  ```

  What address you see depends on the Docker network configuration, so read it
  from the message.
- **IPv6.** A device that reaches the server over IPv6 is matched by its IPv6
  address. In our test, a client with only an IPv4 address was unknown when the
  same device sent the request over IPv6:

  ```text
  Ignoring request to auth address :: port 1812 bound to server default from unknown client 2001:db8::10 port 45033 proto udp
  ```

  A `client` block holds one address, so add a second block for the IPv6
  address. `ipaddr` accepts IPv6 addresses:

  ```text
  client office-ap-01-v6 {
  	ipaddr = 2001:db8::10
  	secret = "REPLACE-WITH-THE-SECRET-OF-OFFICE-AP-01"
  }
  ```

Before you add a NAT or Docker gateway address as a client, consider what else
uses it. Every device whose requests come through that address will match the
same client entry and use the same secret.

### The client is in a file the server does not load

Check which files the server reads:

```bash
sudo freeradius -XC | grep 'including'
```

The package installation on Ubuntu reads `/etc/freeradius/3.0/clients.conf`,
the official Docker image reads `/etc/freeradius/clients.conf`. A client in a
separate file is loaded only when `clients.conf` includes it. In our test, a
client in `clients.d/office-ap-01.conf` stayed unknown until we added this
line at the end of `clients.conf`:

```text
$INCLUDE clients.d/
```

After that, the check lists the file:

```text
including files in directory /etc/freeradius/clients.d/
including configuration file /etc/freeradius/clients.d/office-ap-01.conf
```

If FreeRADIUS runs in Docker with `clients.conf` mounted as a single file,
checks inside the container can show an old version of the file. Tools that
replace the file, such as `sed -i`, create a new file on the host. In our test,
`grep` inside the container did not find the new client, and `freeradius -XC`
inside the container checked the old file. After a container restart the new
file was loaded. Mounting the whole configuration directory avoids this.

### The change has not been applied

FreeRADIUS reads static clients at startup. In our test, a client saved to the
loaded `clients.conf` remained unknown until the restart:

```text
Ignoring request to auth address * port 1812 bound to server default from unknown client 192.0.2.10 port 54783 proto udp
```

A reload does not help: on the Ubuntu package, `systemctl reload freeradius`
sends a HUP signal, and FreeRADIUS lead developer Alan DeKok writes that
["You can't reload clients.conf via a HUP."](https://lists.freeradius.org/pipermail/freeradius-users/2021-July/100451.html)
Restart the server as shown in [Confirm the fix](#confirm-the-fix).

### The client belongs to another virtual server

A `client` block inside a `server` section is known only to the `listen`
sockets of that section. The comments in the stock `sites-available/example`
put it this way: if the client sends a request to a different socket, the
server will treat it as an unknown client.

The debug output lists the sockets and their virtual servers:

```text
Listening on auth address * port 1812 bound to server default
Listening on auth address * port 1821 bound to server branch
```

In our test, `office-ap-01` was defined inside `server branch`. Its requests to
port `1821` were processed, and its requests to port `1812` were ignored:

```text
Ignoring request to auth address * port 1812 bound to server default from unknown client 192.0.2.10 port 37215 proto udp
```

Either configure the device to send to the port of its virtual server, or
define the client outside any `server` section in `clients.conf`.

## Confirm the fix

Check the configuration, restart FreeRADIUS, and send the request again:

```bash
# Package installation (systemd)
sudo freeradius -XC
sudo systemctl restart freeradius

# Docker
docker exec <freeradius-container> freeradius -XC
docker restart <freeradius-container>
```

The check must end with `Configuration appears to be OK`. FreeRADIUS does not
start with a broken configuration.

Then repeat the request that failed. Send it from the device's address, to the
same server address, port, and IP version as in the error message. `radtest`
is in the `freeradius-utils` package and in the official Docker image:

```bash
radtest test-user test-password 192.0.2.1 0 'REPLACE-WITH-THE-CLIENT-SECRET'
```

The server argument also takes a port, and an IPv6 address in brackets:

```bash
# Client of the branch virtual server on port 1821
radtest test-user test-password 192.0.2.1:1821 0 'REPLACE-WITH-THE-CLIENT-SECRET'

# Request over IPv6
radtest test-user test-password '[2001:db8::1]' 0 'REPLACE-WITH-THE-CLIENT-SECRET'
```

`radtest` checks authentication only. If the error was for the `acct` socket,
send an accounting request with `radclient`, which is in the same package:

```bash
echo 'Acct-Status-Type = Start, User-Name = test-user, Acct-Session-Id = test-1, NAS-IP-Address = 192.0.2.10' \
  | radclient 192.0.2.1:1813 acct 'REPLACE-WITH-THE-CLIENT-SECRET'
```

Expected result:

```text
Received Accounting-Response Id 46 from 192.0.2.1:1813 to 192.0.2.10:34523 length 20
```

For authentication, treat the disappearance of the error and a successful
login as two separate results. In our test, after the restart:

- A user that does not exist got `Access-Reject`. The server no longer
  ignored the request, so the client entry worked:

  ```text
  Received Access-Reject Id 215 from 192.0.2.1:1812 to 192.0.2.10:39249 length 38
  ```

- The test user with the right password got `Access-Accept`:

  ```text
  Received Access-Accept Id 111 from 192.0.2.1:1812 to 192.0.2.10:47056 length 38
  ```

An `Access-Reject` after the fix points to the user's credentials or the
authentication policy, not to `clients.conf`.

If there is still no reply but the `unknown client` message is gone, the
server now recognizes the client and drops the request for another reason. The
log names it. The two common ones are a wrong shared secret
(`invalid Message-Authenticator`) and a device that does not send
Message-Authenticator. Both are explained in the clients.conf guide under
[Common errors](/blog/freeradius-clients-conf/#common-errors) and
[Message-Authenticator and BlastRADIUS settings](/blog/freeradius-clients-conf/#message-authenticator-and-blastradius-settings).

If the log shows nothing at all for the request, the request did not reach
FreeRADIUS. Check the server address and port on the device, firewalls on the
way, and the `Listening on` lines in the debug output.

## Frequently asked questions

### Does the shared secret matter for an unknown client error?

No. FreeRADIUS looks up the client by source address before it checks the
secret. In our test, requests with arbitrary secrets produced the same
message. A wrong secret for a known client produces a different message,
`invalid Message-Authenticator`.

### Does NAS-IP-Address have to match ipaddr?

No. The client is selected by the source IP address of the packet. A request
with the right `NAS-IP-Address` from a different source address is still
ignored.

### Will systemctl reload fix it?

No. A reload sends a HUP signal, and static clients from `clients.conf` are not
reloaded on HUP. Restart FreeRADIUS after adding or changing a client.

### Where does FreeRADIUS log unknown client errors?

In debug mode (`freeradius -X`), on the terminal. Otherwise in `radius.log` in
the log directory, `/var/log/freeradius/radius.log` on the Ubuntu package. With
the official Docker image, `docker logs <freeradius-container>` shows the
output.

### Why does the message show my Docker gateway address?

Docker port publishing can change the source address of requests. In our
tests, requests to a published port arrived from the gateway of a Docker
network. FreeRADIUS matches clients against that address.

### Why does the error mention port 1813?

Port `1813` is for accounting. The device sends accounting requests to it, and
the same client entry must match them. Look up the source address the same way
as for authentication, and test the fix with an accounting request, as shown
under [Confirm the fix](#confirm-the-fix).

## Add the client from a web interface

The fix is always the same: a correct `client` block in the loaded
`clients.conf` and a restart. If you manage many devices, you can do the first
part with [RadiusDeck](https://github.com/radiusdeck/radiusdeck), an
open-source web interface for `clients.conf`. It edits the file in place,
which avoids the single-file Docker mount problem described above, and creates
a backup before each change. You still apply the change by restarting
FreeRADIUS, or through an optional reload sidecar.
[FreeRADIUS Web GUI: How to Manage RADIUS Clients](/blog/freeradius-web-gui/)
shows the setup step by step, from installation to a successful `radtest`
request.

## Sources

- Comments in the stock `clients.conf`, `radiusd.conf`, and
  `sites-available/example` of FreeRADIUS 3.2.10.
- [Reload Freeradius server without Restart](https://lists.freeradius.org/pipermail/freeradius-users/2021-July/100451.html),
  freeradius-users mailing list, July 2021.
- [FreeRADIUS clients.conf: Examples and Best Practices](/blog/freeradius-clients-conf/).
