---
title: Practical FreeRADIUS guides
---

<p class="eyebrow">Configuration · Operations · Troubleshooting</p>

# Make sense of your FreeRADIUS clients.

Practical guides to client configuration, troubleshooting, and managing
FreeRADIUS with RadiusDeck.
{: .lead }

## Start with the project

RadiusDeck is a lightweight web interface for FreeRADIUS client configuration.
Use it to manage the access points, switches, and VPN gateways that send requests
to your server. End-user accounts and authentication policies are configured
separately in FreeRADIUS.

The project README includes installation instructions, screenshots, and a demo
that walks through adding a client and checking a real authentication request.

[Explore RadiusDeck on GitHub →](https://github.com/radiusdeck/radiusdeck){: .button }

## Guides

{% if site.posts.size > 0 -%}
<ul class="post-list">
{%- for post in site.posts limit: 3 %}
  <li>
    <h3><a href="{{ post.url | relative_url }}">{{ post.title | escape }}</a></h3>
    <p>{{ post.description | strip_html | normalize_whitespace | escape }}</p>
  </li>
{%- endfor %}
</ul>

[All guides →]({{ '/blog/' | relative_url }})
{%- else -%}
Our first guides will cover `clients.conf` examples, diagnosing unknown client
errors, and managing RADIUS clients through the web interface.

In the meantime, browse the
[Community documentation]({{ site.product_url }}/tree/main/docs/community)
for configuration and operating details.
{%- endif %}
