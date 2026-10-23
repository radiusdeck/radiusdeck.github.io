---
title: FreeRADIUS guides
description: >-
  Tested FreeRADIUS guides on clients.conf, RADIUS client troubleshooting,
  and managing clients with the RadiusDeck web interface.
permalink: /blog/
---

# FreeRADIUS guides

Each guide is checked on an isolated test setup. The tested versions and the
date of the last check are listed at the top of every article.
{: .lead }

{% if site.posts.size > 0 -%}
<ul class="post-list">
{%- for post in site.posts %}
  <li>
    <h2><a href="{{ post.url | relative_url }}">{{ post.title | escape }}</a></h2>
    <p>{{ post.description | strip_html | normalize_whitespace | escape }}</p>
    <p class="post-meta"><time datetime="{{ post.date | date_to_xmlschema }}">{{ post.date | date: "%B %-d, %Y" }}</time></p>
  </li>
{%- endfor %}
</ul>
{%- else -%}
The first guides are in preparation. In the meantime, see the
[RadiusDeck documentation]({{ site.product_url }}/tree/main/docs/community).
{%- endif %}
