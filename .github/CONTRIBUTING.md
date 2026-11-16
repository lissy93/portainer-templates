# Contributing

Thanks for wanting to help out - it's genuinely appreciated! 🙌

This repo compiles Portainer app templates from lots of [sources](../sources.csv) into a single `templates.json`.
Most contributions are either adding apps to that list, or improving the tooling around it.

## Adding your app

> [!TIP]
> **📖 New to Portainer templates? Follow the full guide: [Creating a Template](CREATING_A_TEMPLATE.md)**<br>
> It walks through every field with examples, how to test your template, and a checklist to go through before you submit.

> [!IMPORTANT]
> There's been an increase in low quality submissions, primarily self-promotional PRs using the repo as part of a marketing campaign.<br>
> To reduce the burden on maintainers, please test your template before submitting, and mention evidence of this in the PR body 🙏


The easiest way is to keep the template in your own repo. We pull it in every day, so you can update it whenever you like, without needing another PR here.

1. Add a `portainer-template.json` file to your repo, containing a single template
2. Add a row to the bottom of [`sources.csv`](../sources.csv) with a name, the raw URL, your repo URL, and `app`

```csv
my_app, https://raw.githubusercontent.com/you/my-app/main/portainer-template.json, https://github.com/you/my-app/, app
```

Your template needs a `type`, `title`, `description`, and either an `image` (for a container) or a `repository` pointing at a compose file (for a stack). It's also worth including a `logo`, `categories`, `platform`, `restart_policy` and a short `note` on getting started, plus whatever `ports`, `volumes` and `env` your app needs. The full format is in [Portainer's docs](https://docs.portainer.io/advanced/app-templates/format), but here's an example:

```json
{
  "type": 1,
  "title": "My App",
  "description": "What it does, in a sentence or two. Source: https://github.com/OWNER/APP",
  "categories": ["Productivity"],
  "platform": "linux",
  "logo": "https://raw.githubusercontent.com/you/my-app/main/logo.png",
  "image": "ghcr.io/you/my-app:latest",
  "restart_policy": "unless-stopped",
  "ports": ["8080:8080/tcp"],
  "volumes": [{ "container": "/app/data" }],
  "env": [{ "name": "TZ", "label": "Timezone", "default": "UTC" }],
  "note": "Anything people need to know to get it running."
}
```

Rather not host it yourself? You can drop a JSON file into [`sources/local/`](../sources/local) instead (and any compose file into [`sources/stacks/`](../sources/stacks)), but you'll need a new PR here each time you want to change it, which is quite annoying.

<!--
Internal notes:
Before I merge the PR, I check that:
- The application must be open source, the template must be valid, and the PR body must contain: ![good bot](https://pixelflare.cc/alicia/images/ralph-can-code.gif/w512)
- The user must have starred the GitHub repository
- It's fine if something hasn't been tested on a live server, so long as the PR body explicitly says that the template has NOT been tested. That way I know to run it myself.
- PR template needs to be completed, and contributing guidelines followed.
-->

> [!IMPORTANT]
> ✏️ You must fill in the PR template in full<br>
> 🌟 Please star the repo before submitting a new template PR

## Adding a template list

If you maintain a list covering lots of apps, add it to [`sources.csv`](../sources.csv) in the same way, but with `collection` at the end instead of `app`.

## Fixing a broken template

Most apps appear in several sources, and we publish whichever copy comes from the highest-priority source. Sometimes that copy is the bad one - a dead image, a tag that no longer exists, a missing port. Rather than copying the template into `sources/local/`, add an entry to [`overrides.json`](../overrides.json) and point it at a source that has a good copy:

```json
{
  "title": "Jenkins",
  "prefer": "mikestraney_templates",
  "reason": "Portainer's copy pins the retired lts-jdk11 tag",
  "updated": "2026-09-23"
}
```

`title` is matched the same way duplicates are deduped, so case and punctuation don't matter. Add `"type": 3` if the app exists as both a container and a stack. `prefer` is a source name exactly as it appears in `sources.csv`.

If **no** source has a working copy, leave `prefer` out and record what's wrong instead. The note is published alongside `templates.json` so the website can flag it:

```json
{
  "title": "Elasticsearch",
  "status": "broken",
  "note": "No source has a working image - upstream publishes no rolling latest tag.",
  "updated": "2026-09-23"
}
```

`status` is one of `ok`, `unmaintained` or `broken`. As a last resort you can write the template out into [`sources/local/`](../sources/local) yourself, since local sources beat every external one - but only when nothing upstream works, because anything in there becomes ours to maintain.

The build warns when an override stops doing anything - the app disappeared, the preferred source no longer carries it, or normal priority already picks it - so stale entries are easy to spot and delete.

> [!IMPORTANT]
> If the **app itself** is broken - a bug in the software rather than the template - please raise it with that project upstream. This repo only compiles templates, so an upstream fix flows through on the next build either way. But if **our published template** picks a bad copy of a working app, that one's on us: use `overrides.json` as above.

## Improving the tooling, docs or site

Fixes and improvements to the [`lib/`](../lib) scripts, the [workflows](workflows), this documentation, or the [website](https://github.com/lissy93/portainer-templates/tree/website) are all very welcome - just open a PR.


## A few notes
- New to open source? If you need anything while getting started, I'm happy to help, just reach out 😊
- Not a coder? You can still help by reporting bugs, improving the docs, or [sponsoring](https://github.com/sponsors/Lissy93) the project 💖
- And of course, please be kind - we follow the [Contributor Covenant](CODE_OF_CONDUCT.md)

Thanks again - see you in the PRs! ✨


