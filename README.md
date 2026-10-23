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

The checker requires the homepage and 404 page, then verifies local `href` and
`src` targets and HTML fragment IDs. It does not check external URLs or CSS URLs.
Also inspect the homepage on a narrow screen before publishing.

The initial production build, frozen dependency check, and generated local
links passed on 2026-10-23 with Ruby 3.4.12 and Bundler 2.6.9. Browser rendering
and GitHub-hosted workflows have not yet been verified.

## Publishing

In repository settings, select **Pages → Build and deployment → Source →
GitHub Actions**. This setting has already been selected by the repository owner.

- Pull requests into `main` run the **Check site** workflow.
- Pushes to `main` run checks and **Publish site**. Publication repeats the build
  and link checks, and uploads only `_site/` after they pass.
- **Publish site** can also be run manually from `main` in the Actions tab.
- The deployment uses the `github-pages` environment and the built-in GitHub
  token. Configure the environment's deployment branch rule to allow only `main`.

Pushing this scaffold to `main` will attempt to publish the initial homepage.
The first public deployment has not yet been verified.

## Troubleshooting and rollback

Open the failed workflow in **Actions** and inspect the failing step. Dependency
or build failures must be resolved before deployment. If the build passes but
deployment fails, check the Pages source and `github-pages` environment rules.

To undo a published change, revert its commit, verify the resulting build, and
push the revert to `main`. This triggers publication of the restored content.

## Next stage

Add the article layout, blog index, About page, sitemap, RSS, and the first three
reviewed guides. Article URLs follow `/blog/<slug>/`.
