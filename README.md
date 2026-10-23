# RadiusDeck Blog

Practical FreeRADIUS guides: client configuration, troubleshooting, and
web-based management with RadiusDeck.

Target site: <https://radiusdeck.github.io/>.
Product repository: <https://github.com/radiusdeck/radiusdeck>.

## Local setup

Install the Ruby version in `.ruby-version`, Python 3.10 or newer for the link
checker, and Bundler 2.6.9. Then run:

```bash
gem install bundler -v 2.6.9
bundle _2.6.9_ config set --local path vendor/bundle
bundle _2.6.9_ install
bundle _2.6.9_ exec jekyll serve
```

Open <http://127.0.0.1:4000/>. The site uses Jekyll 4.4.1 and local CSS.

Dependencies are recorded in `Gemfile.lock`, including the Linux CI platform.
Both workflows use `BUNDLE_FROZEN: 'true'` to enforce the lock file. Commit any
intentional dependency updates together with the updated lock file.

GitHub Actions are pinned to the commits of these upstream releases:
[checkout v6.1.0](https://github.com/actions/checkout/releases/tag/v6.1.0),
[setup-ruby v1.334.0](https://github.com/ruby/setup-ruby/releases/tag/v1.334.0),
[upload-pages-artifact v5.0.0](https://github.com/actions/upload-pages-artifact/releases/tag/v5.0.0),
and [deploy-pages v5.0.1](https://github.com/actions/deploy-pages/releases/tag/v5.0.1).

## Check the production build

```bash
JEKYLL_ENV=production bundle _2.6.9_ exec jekyll build --strict_front_matter
python3 scripts/check_site.py
```

The checker requires the homepage, 404 page, `sitemap.xml`, `feed.xml`, and
`robots.txt`. It verifies local `href` and `src` targets and HTML fragment IDs.
For every page except 404, it requires a title, a meta description, a canonical
URL that matches the page, and no `noindex`; the 404 page must be `noindex`.
The sitemap must list exactly the indexable pages, `robots.txt` must point to it,
and JSON-LD blocks must parse. External URLs and CSS URLs are not checked.
Also inspect new or changed pages at phone width before publishing.

The production build, frozen dependency check, and checker passed on
2026-10-23 with Ruby 3.4.12 and Bundler 2.6.9. The same day, the homepage,
`/blog/`, `/about/`, 404, and a draft article were rendered in headless Chromium
at 375 px and 1280 px without horizontal page scrolling. The GitHub-hosted
workflow runs have not yet been reviewed.

## Drafts

Article drafts live in `_drafts/`, which is ignored by Git, so unfinished text
does not appear in this public repository. Preview and check them locally:

```bash
bundle _2.6.9_ exec jekyll serve --drafts
JEKYLL_ENV=production bundle _2.6.9_ exec jekyll build --strict_front_matter --drafts
python3 scripts/check_site.py
```

The workflows build without `--drafts`, so CI does not check draft content.
To publish, move the reviewed file to `_posts/YYYY-MM-DD-<slug>.md` and add it
in the release pull request. The URL stays `/blog/<slug>/`.

## Publishing

In repository settings, select **Pages → Build and deployment → Source →
GitHub Actions**. This setting has already been selected by the repository owner.

- Pull requests into `main` run the **Check site** workflow.
- Pushes to `main` run checks and **Publish site**. Publication repeats the build
  and link checks, and uploads only `_site/` after they pass.
- **Publish site** can also be run manually from `main` in the Actions tab.
- The deployment uses the `github-pages` environment and the built-in GitHub
  token. Configure the environment's deployment branch rule to allow only `main`.

The first deployment of the initial homepage to <https://radiusdeck.github.io/>
was confirmed by the repository owner.

## Troubleshooting and rollback

Open the failed workflow in **Actions** and inspect the failing step. Dependency
or build failures must be resolved before deployment. If the build passes but
deployment fails, check the Pages source and `github-pages` environment rules.

To undo a published change, revert its commit, verify the resulting build, and
push the revert to `main`. This triggers publication of the restored content.

## Site structure

| Path | Purpose |
| --- | --- |
| `_layouts/default.html` | Page shell: header navigation, footer |
| `_layouts/post.html` | Article: title, author, publication, update and test dates, related guides |
| `_includes/head.html` | Title, description, canonical URL, Open Graph, feed link, JSON-LD (`TechArticle` for articles, `WebSite` for the homepage) |
| `blog.md`, `about.md` | `/blog/` list of guides and `/about/` page |
| `sitemap.xml`, `feed.xml`, `robots.txt` | Liquid templates; no Jekyll plugins are used |

Article front matter:

```yaml
title: "FreeRADIUS clients.conf: Examples and Best Practices"
description: One or two sentences for search results and the guide list.
last_modified_at: 2026-11-02   # only after a substantial update
tested:
  date: 2026-10-23
  environment: Official FreeRADIUS Docker image
  freeradius: "3.2.10"
  radiusdeck: "0.1.0"
related:
  - /blog/<slug>/
```

The author (`RadiusDeck team`) and the `post` layout come from `_config.yml`
defaults. The layout prints the title as the page heading, so the article body
starts without an H1. Related guides appear only when the target article is
published.

`robots.txt` allows all crawlers, including AI search crawlers.
