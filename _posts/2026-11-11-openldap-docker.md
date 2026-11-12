---
title: "OpenLDAP in Docker: Run It with ldap:// and ldaps://"
description: >-
  Run OpenLDAP 2.6 in Docker as a disposable lab with the instantlinux/openldap
  image: add a test user, switch to ldaps:// with a test CA, and check the
  connection from the host and from another container.
tested:
  date: 2026-11-06
  environment: Docker 29.9.3 on Ubuntu 24.04
  openldap: "2.6.15, image instantlinux/openldap:2.6.15-r0"
related:
  - /blog/freeradius-ldap/
---

**Short answer:** This guide builds a disposable OpenLDAP lab in Docker with
one test user, first over `ldap://` and then over `ldaps://` with a test CA.
Each part is checked with `ldapwhoami` from the host and from another
container, by the name `ldap.example.org`.

* TOC
{:toc}

## Tested with

- OpenLDAP 2.6.15 on Alpine 3.24, image
  `instantlinux/openldap:2.6.15-r0@sha256:54853fb9a080be0ea06ba02dad312c0eb5f105ea293e1fd2d90460cc71886e1a`.
- LDAP clients on the host: `ldap-utils` 2.6.10 from Ubuntu 24.04.
- Docker 29.9.3 on Linux.

Use this setup only as a test lab that you can delete afterwards. Part 2
switches to TLS by deleting the directory and starting over. The domain
`example.org` and the passwords are examples.

## What you will run

One container, `openldap`, on a Docker network `ldap-net`. Inside that
network it answers to `ldap.example.org`. The host reaches it through a port
published on `127.0.0.1`, and any other container on `ldap-net` reaches it
directly:

```text
host:      ldapwhoami -> 127.0.0.1:389 or :636 -> openldap
container: ldapwhoami -> ldap-net -> ldap.example.org:389 or :636 -> openldap
```

You need:

- Docker and OpenSSL on the host.
- LDAP clients on the host: `sudo apt install ldap-utils` on Debian and
  Ubuntu.
- The same name on the host. Add this line to `/etc/hosts`:

  ```text
  127.0.0.1 ldap.example.org
  ```

The name matters for `ldaps://`: the client checks it against the server
certificate. Using it from the start keeps the commands the same in both
parts.

Pin the image in a variable. The commands below use it:

```bash
IMG=instantlinux/openldap:2.6.15-r0@sha256:54853fb9a080be0ea06ba02dad312c0eb5f105ea293e1fd2d90460cc71886e1a
```

## Part 1: OpenLDAP with ldap://

### Start the server

```bash
docker network create ldap-net

docker run -d --name openldap --hostname ldap \
  --network ldap-net --network-alias ldap.example.org \
  -e SLAPD_FQDN=example.org -e SLAPD_ORGANIZATION=Example \
  -e SLAPD_ROOTPW=admin-pass-change-me \
  -v openldap-config:/etc/openldap \
  -v openldap-data:/var/lib/openldap/openldap-data \
  -p 127.0.0.1:389:389 \
  --entrypoint /bin/sh \
  "$IMG" /usr/local/bin/entrypoint.sh
```

`SLAPD_FQDN` sets the base of the directory, `dc=example,dc=org`, and the
administrator `cn=admin,dc=example,dc=org` gets the password from
`SLAPD_ROOTPW`.

**Why `--entrypoint /bin/sh`.** Without it, the container exits within
seconds of the first start:

```text
<= str2entry: str2ad(add): attribute type undefined
slapadd: could not parse entry (line=1)
```

The startup script is written for `sh -e`, which stops at the first failed
command. It loads the image's own LDIF files with `slapadd`, and one of
them, `0-hashedpassword.ldif`, is written for `ldapmodify`, so `slapadd`
rejects it. Running the script with plain `sh` turns off `-e` for the whole
script: the failed `slapadd` no longer stops it, and neither would any other
failed step. The two error lines above stay in the log. This is acceptable
for a lab because the next steps check the result: the administrator logs
in, and a user can be added and log in.

The server needs a few seconds to start. A command run right after
`docker run` or `docker restart` can fail with
`Can't contact LDAP server (-1)`; wait and run it again. On the first start,
the server is ready when this line appears:

```bash
docker logs openldap 2>&1 | grep 'slapd starting'
```

If you have already started the container without the workaround, do not
just run `docker start`. The container comes up, but the setup never
finished, and the directory has no base entry: every search answers
`No such object (32)`. Remove the container and its volumes, then run the
command above again. This deletes everything the container stored:

```bash
docker rm -fv openldap
docker volume rm openldap-config openldap-data
```

The `-v` in `docker rm -fv` also removes two anonymous volumes the image
declares, `/etc/openldap/prepopulate` and `/etc/ssl/openldap`.

### Add a user and check from the host

Check the administrator first:

```bash
ldapwhoami -x -H ldap://ldap.example.org \
  -D cn=admin,dc=example,dc=org -w admin-pass-change-me
```

```text
dn:cn=admin,dc=example,dc=org
```

A new directory has the base entry and the password-policy entries under
`ou=Policies`. Add a test user:

```bash
cat > users.ldif <<'EOF'
dn: ou=users,dc=example,dc=org
objectClass: organizationalUnit
ou: users

dn: uid=alice,ou=users,dc=example,dc=org
objectClass: inetOrgPerson
uid: alice
cn: Alice
sn: Example
mail: alice@example.org
EOF

ldapadd -x -H ldap://ldap.example.org \
  -D cn=admin,dc=example,dc=org -w admin-pass-change-me -f users.ldif
ldappasswd -x -H ldap://ldap.example.org \
  -D cn=admin,dc=example,dc=org -w admin-pass-change-me \
  -s alice-pass-change-me uid=alice,ou=users,dc=example,dc=org
```

`ldappasswd` lets the server hash the password itself. With this image and
the workaround above, the scheme is `{PBKDF2-SHA512}`. Now log in as the
user:

```bash
ldapwhoami -x -H ldap://ldap.example.org \
  -D uid=alice,ou=users,dc=example,dc=org -w alice-pass-change-me
```

```text
dn:uid=alice,ou=users,dc=example,dc=org
```

With a wrong password the answer is `ldap_bind: Invalid credentials (49)`.

alice can log in, but she cannot read any entries, not even her own. The
image's access rules let only the administrator, and root over the local
`ldapi://` socket, read the directory. A search as alice returns
`No such object (32)` rather than an access error, so the client does not
learn whether an entry exists.

### Check from another container

The image includes the LDAP clients, so the same image works as a client.
Replace its entrypoint with the tool you need:

```bash
docker run --rm --network ldap-net --entrypoint ldapwhoami "$IMG" \
  -x -H ldap://ldap.example.org \
  -D uid=alice,ou=users,dc=example,dc=org -w alice-pass-change-me
```

```text
dn:uid=alice,ou=users,dc=example,dc=org
```

`--network ldap-net` is required. The name `ldap.example.org` exists only
inside that network, and without it the client answers
`Can't contact LDAP server (-1)`.

## Part 2: Start over with ldaps://

The startup script writes the TLS settings into the server configuration only
during the first setup. If you mount certificates into the container from
part 1, they are silently ignored: the server keeps listening on port 389
without TLS. This guide therefore builds a new directory. Part 2 deletes
the container and both volumes from part 1, with all entries and settings
in them, and loads the test user again.

### Create a test certificate

A test CA and a server certificate for `ldap.example.org`. The CA key stays
in `ca/`; `ldap-tls/` holds what the container needs, with the file names
the startup script expects.

```bash
mkdir -p ca ldap-tls
openssl req -x509 -newkey rsa:2048 -nodes -days 365 -subj "/CN=Example Lab CA" \
  -addext basicConstraints=critical,CA:TRUE \
  -addext keyUsage=critical,keyCertSign,cRLSign \
  -keyout ca/ca.key -out ca/ca_cert.pem
openssl req -newkey rsa:2048 -nodes -subj "/CN=ldap.example.org" \
  -keyout ldap-tls/tls.key -out ca/tls.csr
printf 'subjectAltName=DNS:ldap.example.org\nextendedKeyUsage=serverAuth\n' \
  > ca/tls.ext
openssl x509 -req -in ca/tls.csr -CA ca/ca_cert.pem -CAkey ca/ca.key \
  -CAcreateserial -days 365 -extfile ca/tls.ext -out ldap-tls/tls.crt
cp ca/ca_cert.pem ldap-tls/
chmod 0644 ldap-tls/tls.key
```

The server inside the container runs as UID 100 and has to read the key.
Mode `0644` makes the key readable by every user on the host, which is
acceptable for a test machine only.

### Fix the startup script for restarts

With certificates, the first start listens on `ldaps:///`, port 636. After
`docker restart`, the server listens on `ldap:///`, port 389, and port 636
is closed. Line 5 of the startup script sets `SLAPD_URLPREFIX=ldap`
unconditionally, and the switch to `ldaps` happens only inside the
first-setup block, which a restart skips. Setting `SLAPD_URLPREFIX` in the
environment does not help, because line 5 overwrites it.

Copy the script out of the running container and let line 5 keep a value
from the environment:

```bash
docker cp openldap:/usr/local/bin/entrypoint.sh ./ldap-entrypoint.sh
sed -i 's/^SLAPD_URLPREFIX=ldap$/SLAPD_URLPREFIX=${SLAPD_URLPREFIX:-ldap}/' ldap-entrypoint.sh
grep -n '^SLAPD_URLPREFIX' ldap-entrypoint.sh
```

```text
5:SLAPD_URLPREFIX=${SLAPD_URLPREFIX:-ldap}
```

### Start the server with TLS

This deletes the lab directory from part 1:

```bash
docker rm -fv openldap
docker volume rm openldap-config openldap-data

docker run -d --name openldap --hostname ldap \
  --network ldap-net --network-alias ldap.example.org \
  -e SLAPD_FQDN=example.org -e SLAPD_ORGANIZATION=Example \
  -e SLAPD_ROOTPW=admin-pass-change-me \
  -e SLAPD_URLPREFIX=ldaps \
  --mount type=bind,src="$PWD/ldap-tls",dst=/etc/ssl/openldap,readonly \
  --mount type=bind,src="$PWD/ldap-entrypoint.sh",dst=/usr/local/bin/entrypoint.sh,readonly \
  -v openldap-config:/etc/openldap \
  -v openldap-data:/var/lib/openldap/openldap-data \
  -p 127.0.0.1:636:636 \
  --entrypoint /bin/sh \
  "$IMG" /usr/local/bin/entrypoint.sh
```

Only port 636 is published. Port 389 is closed in this mode.

The files from the host are mounted with `--mount`. If the source
path is wrong, `-v` silently creates an empty directory on the host, owned
by root, and mounts it. `--mount` refuses to start instead:

```text
docker: Error response from daemon: invalid mount config for type "bind": bind source path does not exist: ...
```

The named volumes stay with `-v`: here you want Docker to create a missing
volume.

### Check from the host

Tell the clients which CA to trust. `LDAPTLS_CACERT` is the environment form
of the `TLS_CACERT` option from `ldap.conf`:

```bash
export LDAPTLS_CACERT="$PWD/ca/ca_cert.pem"

ldapadd -x -H ldaps://ldap.example.org \
  -D cn=admin,dc=example,dc=org -w admin-pass-change-me -f users.ldif
ldappasswd -x -H ldaps://ldap.example.org \
  -D cn=admin,dc=example,dc=org -w admin-pass-change-me \
  -s alice-pass-change-me uid=alice,ou=users,dc=example,dc=org
ldapwhoami -x -H ldaps://ldap.example.org \
  -D uid=alice,ou=users,dc=example,dc=org -w alice-pass-change-me
```

```text
dn:uid=alice,ou=users,dc=example,dc=org
```

Restart the container, wait a few seconds, and run `ldapwhoami` again. With
the fixed script, the answer is the same after `docker restart` and after
`docker stop` with `docker start`.

### Check from another container

The client container needs the CA file too:

```bash
docker run --rm --network ldap-net \
  --mount type=bind,src="$PWD/ca/ca_cert.pem",dst=/ca.pem,readonly \
  -e LDAPTLS_CACERT=/ca.pem \
  --entrypoint ldapwhoami "$IMG" \
  -x -H ldaps://ldap.example.org \
  -D uid=alice,ou=users,dc=example,dc=org -w alice-pass-change-me
```

```text
dn:uid=alice,ou=users,dc=example,dc=org
```

## Troubleshooting

### "Can't contact LDAP server (-1)"

The clients print this one line for many different problems, including
every kind of TLS failure. The host clients from Ubuntu show more only in
debug output:

```bash
ldapwhoami -d1 -x -H ldaps://ldap.example.org \
  -D uid=alice,ou=users,dc=example,dc=org -w alice-pass-change-me 2>&1 |
  grep -E '^TLS:|errno|getaddrinfo'
```

The messages below are what we saw in each case on our test machine. The
same message can have other causes, so use the table as a starting point.

| Case in our test | What `-d1` showed | What to check |
|---|---|---|
| Container stopped, or the port not published; also `ldap://` when only 636 is published | `connect errno: 111` | `docker ps`, the `-p` option, the URL scheme |
| Startup script not fixed, after a restart: the port is published, but the server inside listens on 389 | `TLS: can't connect: Error in the pull function..` | [The fixed script](#fix-the-startup-script-for-restarts) |
| Name does not resolve: no `/etc/hosts` line, or a container outside `ldap-net` | `getaddrinfo failed: No address associated with hostname` | `/etc/hosts`, `--network ldap-net` |
| `LDAPTLS_CACERT` not set | `TLS: peer cert untrusted or revoked (0x42)` | The path to `ca_cert.pem` |
| Connected by IP: `ldaps://127.0.0.1` | `TLS: hostname (127.0.0.1) does not match common name in certificate (ldap.example.org)` | Connect by the name in the certificate |

The clients in the Alpine-based image are built with OpenSSL and print the
TLS cause right away, as `additional info`:

```text
ldap_sasl_bind(SIMPLE): Can't contact LDAP server (-1)
	additional info: error:0A000086:SSL routines::certificate verify failed (self-signed certificate in certificate chain)
```

A connection by the container name, `ldaps://openldap`, fails there with
`TLS: hostname does not match name in peer certificate`.

## Clean up

```bash
docker rm -fv openldap
docker volume rm openldap-config openldap-data
docker network rm ldap-net
```

## Limitations

- The access rules are not changed. A service such as FreeRADIUS needs its
  own account and a rule that lets it read users.
- `SLAPD_ROOTPW` is visible to anyone who can run `docker inspect`. The
  image can read the password from a Docker secret instead
  (`SLAPD_ROOTPW_SECRETNAME`); we did not test it.
- The CA is a test CA, and the server key is readable by all users of the
  host.
- StartTLS on port 389 is not covered. With the fixed script and
  `SLAPD_URLPREFIX=ldaps`, the server does not listen on 389 at all.
- Both workarounds were checked with the image digest above. A newer image
  may fix the startup script or change its behavior.

## Frequently asked questions

### Can I enable TLS on a directory that already has data?

Not with this image's startup script: it applies TLS settings only to a new
directory. Two ways remain, and we tested neither: add the TLS attributes to
`cn=config` with `ldapmodify` as root over `ldapi://`, or export the data
with `slapcat` and import it into a new directory started with
certificates.

## Next steps

The next guide in this series connects FreeRADIUS to this directory over
`ldaps://`, with a service account that can read users.

## Sources

- [instantlinux/openldap](https://hub.docker.com/r/instantlinux/openldap),
  Docker Hub, and its
  [source](https://github.com/instantlinux/docker-tools/tree/main/images/openldap):
  `entrypoint.sh`, `slapd.conf`, environment variables.
- [Using TLS](https://www.openldap.org/doc/admin26/tls.html), OpenLDAP 2.6
  Administrator's Guide: `ldaps://`, StartTLS, `-Z` and `-ZZ`.
- [ldap.conf(5)](https://www.openldap.org/software/man.cgi?query=ldap.conf&sektion=5&apropos=0&manpath=OpenLDAP+2.6-Release):
  `TLS_CACERT` and the `LDAP<option>` environment variables.
- [Bind mounts](https://docs.docker.com/engine/storage/bind-mounts/), Docker
  documentation: `--mount` and `-v` with a missing source path.

