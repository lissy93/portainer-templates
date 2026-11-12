# Creating a Portainer template

This guide walks through writing a Portainer app template for your own app, so people can deploy it from Portainer's template list in a couple of clicks. You'll end up with a single `portainer-template.json` in your repo, which this project pulls in every day.

In a hurry? Copy one of the [examples](#example-a-container), change the details, then work through the [checklist](#checklist). Already done? Skip to [submitting it](#submitting-it).

## Contents

- [Before you start](#before-you-start)
- [Choose a type](#choose-a-type)
- [Example: a container](#example-a-container)
- [Example: a stack](#example-a-stack)
- [The fields](#the-fields)
- [Getting the format right](#getting-the-format-right)
- [Security](#security)
- [Testing it](#testing-it)
- [Checklist](#checklist)
- [Submitting it](#submitting-it)

## Before you start

You'll need:

- A public Docker image of your app, on Docker Hub, GHCR or any registry that doesn't need a login
- A public git repo to hold the template file, and your compose file if you're making a stack
- The app already running under Docker, so you know its ports, data folders and settings

## Choose a type

| Type | What Portainer deploys | Use it when |
|------|------------------------|-------------|
| `1` | One container, from your image | Your image plus some ports, volumes and env vars is all the app needs |
| `3` | A Docker Compose stack, from a compose file in your repo | The app needs other services to run, like a database, cache or worker |

Go with a container if you can, since it's simpler for people to deploy and tweak. But if the app won't start without a database, make it a stack. Shipping a container and asking users to go and set up Postgres themselves isn't a working template.

Type `2` (Swarm stack) also exists, but it only deploys to Swarm, so this guide doesn't cover it.

## Example: a container

A complete type 1 template, put together from the best ones in this project's list. Copy it and change every value to fit your app.

```json
{
  "type": 1,
  "title": "My App",
  "name": "my-app",
  "description": "Self-hosted bookmark manager with full-text search, tags and browser extensions. Source: https://github.com/you/my-app",
  "categories": ["Productivity", "Tools"],
  "platform": "linux",
  "logo": "https://raw.githubusercontent.com/you/my-app/main/docs/logo.png",
  "image": "ghcr.io/you/my-app:1",
  "restart_policy": "unless-stopped",
  "ports": ["8080:8080/tcp"],
  "volumes": [{ "container": "/app/data" }],
  "env": [
    {
      "name": "TZ",
      "label": "Timezone",
      "description": "Used for timestamps and scheduled jobs, e.g. Europe/London",
      "default": "UTC"
    },
    {
      "name": "MYAPP_MAX_UPLOAD_MB",
      "label": "Largest file people can upload, in MB",
      "default": "50"
    },
    {
      "name": "MYAPP_LOG_LEVEL",
      "label": "Log level",
      "select": [
        { "text": "Info", "value": "info", "default": true },
        { "text": "Debug", "value": "debug" }
      ]
    }
  ],
  "note": "On first start My App prints a one-time admin password to the container log. Open <code>http://&lt;your-host&gt;:8080</code> and sign in as <code>admin</code> with it. Everything is stored in the <code>/app/data</code> volume. Docs: <a href=\"https://github.com/you/my-app#readme\" target=\"_blank\">github.com/you/my-app</a>"
}
```

Notice that it deploys without anyone touching the form. Every input has a working default, and the app generates its own admin password instead of shipping one.

## Example: a stack

A type 3 template points at a compose file in your repo, and its env vars fill in the `${VARIABLES}` in that file.

```json
{
  "type": 3,
  "title": "My App",
  "name": "my-app",
  "description": "Self-hosted bookmark manager with full-text search, tags and browser extensions. Source: https://github.com/you/my-app",
  "categories": ["Productivity", "Tools"],
  "platform": "linux",
  "logo": "https://raw.githubusercontent.com/you/my-app/main/docs/logo.png",
  "restart_policy": "unless-stopped",
  "repository": {
    "url": "https://github.com/you/my-app",
    "stackfile": "docker-compose.yml"
  },
  "env": [
    {
      "name": "MYAPP_DB_PASSWORD",
      "label": "Database password (required)",
      "description": "Generate one with: openssl rand -hex 32. Keep it the same when you redeploy, or the app can't reach its database."
    },
    {
      "name": "MYAPP_PUBLIC_URL",
      "label": "Address you'll open My App at",
      "description": "Used to build links in emails. It must match the address in your browser, port included.",
      "default": "http://localhost:8080"
    },
    {
      "name": "MYAPP_PORT",
      "label": "Host port for the web UI",
      "default": "8080"
    }
  ],
  "note": "Set a <b>database password</b> before you deploy (<code>openssl rand -hex 32</code> makes a good one). The stack won't start without it. Then open <code>http://&lt;your-host&gt;:8080</code> and create your account. Docs: <a href=\"https://github.com/you/my-app#readme\" target=\"_blank\">github.com/you/my-app</a>"
}
```

And the `docker-compose.yml` it points at, in the root of your repo:

```yaml
services:
  app:
    image: ghcr.io/you/my-app:1
    restart: unless-stopped
    ports:
      - "${MYAPP_PORT:-8080}:8080"
    environment:
      MYAPP_PUBLIC_URL: ${MYAPP_PUBLIC_URL:-http://localhost:8080}
      MYAPP_DATABASE_URL: postgres://myapp:${MYAPP_DB_PASSWORD:?Set a database password}@db:5432/myapp
    volumes:
      - app-data:/app/data
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:17-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: myapp
      POSTGRES_PASSWORD: ${MYAPP_DB_PASSWORD:?Set a database password}
    volumes:
      - db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U myapp -d myapp"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  app-data:
  db-data:
```

Ideally this is the same compose file your README already tells people to use, so there's only one to maintain. For real stacks published this way, see [Homedex](https://github.com/HarshShah0203/homedex/blob/main/portainer-template.json) and [ReplayHaven](https://github.com/SauerExe/ReplayHaven/blob/main/portainer-template.json).

### Writing the compose file

- Portainer clones your repo's default branch and deploys the file at `stackfile`, a path from the repo root. The repo has to be public.
- The template's env vars only fill in `${VARIABLES}` in the compose file. They don't reach your containers unless the compose file passes them in, like `MYAPP_PUBLIC_URL` above.
- Write optional ones as `${VAR:-default}`, with the same default as the template. A blank field then falls back to the default, and the file still works with a plain `docker compose up`.
- Write required ones as `${VAR:?message}`. If someone leaves it blank, the stack fails with your message instead of starting half configured.
- Use published images. Don't use `build:`.
- Use named volumes. A relative bind mount like `./config:/config` won't see the files in your repo, because by default Portainer resolves it against its own data folder, not a checkout on the host.
- Set `restart: unless-stopped` on every service. Portainer ignores the template's `restart_policy` for stacks.
- Give the database a healthcheck, and make the app wait for it with `depends_on` and `condition: service_healthy`.
- Pin databases to a major version, like `postgres:17-alpine`. Moving to a new major version needs a data migration, so it shouldn't happen during a routine update.
- Only publish ports people need to reach. Services talk to each other over the stack's own network, so the database needs no `ports:`.
- Leave out `container_name`, which stops anyone deploying the stack twice, and the top-level `version:` key, which Compose no longer uses.

## The fields

| Field | Type | Container (1) | Stack (3) |
|-------|------|:-------------:|:---------:|
| `type` | number | required | required |
| `title` | string | required | required |
| `description` | string | required | required |
| `image` | string | required | |
| `repository` | object | | required |
| `categories` | list of strings | expected | expected |
| `logo` | URL | expected | expected |
| `note` | string, basic HTML | expected | expected |
| `platform` | `linux` or `windows` | expected | expected |
| `restart_policy` | string | expected | expected |
| `name` | string | optional | optional |
| `env` | list | optional | optional |
| `ports` | list of strings | optional | in compose file |
| `volumes` | list | optional | in compose file |

"Expected" means the validator warns if it's missing. Treat those warnings as things to fix.

### Title and name

- `title` is your app's name, written the way you brand it, like `Homedex`, `ntfy` or `LibreDB Studio`. No extra words like "Docker" or "Self-hosted", and no version numbers.
- If your app is already in the list, use the same title and type. Your template then replaces the community copy, instead of showing up next to it as a duplicate. Case, spaces and punctuation don't matter when matching, so `AdGuard Home` matches `Adguardhome`. Leave off any `(container)` or `(stack)` the website adds to the end. Search [the website](https://portainer-templates.as93.net) to check.
- `name` pre-fills the container or stack name on the deploy form. A stack can't be deployed until someone fills that box in, so set it to save people the typing. Portainer only accepts lowercase letters, numbers, `-` and `_`, so something like `my-app` is perfect.

### Description

- One or two sentences on what the app does. Portainer shows it in the list next to your logo, so shorter reads better.
- Plain text only. Portainer doesn't render Markdown or HTML here, so a `[link](url)` shows up with its brackets.
- End it with `Source: https://github.com/you/my-app`, pointing at your repo. That's how people get from the list or the website to your project.
- Skip the marketing words like "powerful" or "blazing fast", and just say what it does.

### Categories

Pick one to three, most relevant first, and reuse categories that already exist, spelled exactly the same way. Portainer's category filter matches exact names, so if you tag your app `Gaming` while everything similar uses `Games`, it won't show up alongside them.

Good ones to choose from:

> AI, Analytics, Automation, Backup, Books, Chat, CMS, Cloud, Dashboard, Database, Development, DNS, Documents, Downloaders, Email, File Sharing, Finance, Games, Home Automation, Media, Messaging, Monitoring, Music, Networking, Photos, Productivity, Project Management, Proxy, Remote Desktop, Security, Social, Storage, Tools, Video, VPN, Web, Wiki

Avoid `Other`, `Docker` and `Self-hosted`, since they fit every app here and don't help anyone filter. Also avoid `edge`, which Portainer reserves for Edge templates.

To see every category in use, and how often:

```bash
curl -s https://raw.githubusercontent.com/lissy93/portainer-templates/main/templates.json \
  | jq -r '.templates[].categories[]?' | sort | uniq -c | sort -rn
```

### Logo

- Use your app's own logo, so people recognise it. If you don't have one yet, your GitHub avatar is a fine fallback.
- Square, with a transparent background, as a PNG or SVG at least 128px across. Portainer shows it small, and the website shows it larger.
- Use a stable `https` URL. A file in your repo, linked through `raw.githubusercontent.com` on your default branch, is ideal. Avoid links that expire or might move, like signed CDN links or release assets.
- If the URL isn't valid, the logo gets dropped and Portainer shows a generic icon instead.

### Note

Portainer shows the note on the deploy form. Use it for whatever people need to get going:

- where to open the app, and on which port
- how the first login works, like a default user, a generated password or a setup page
- any required secrets, and how to generate them
- where the data is stored
- known gotchas, like needing HTTPS or an exact public URL
- a link to your docs

It takes basic HTML such as `<b>`, `<code>`, `<br>` and `<a href="...">`. Portainer strips out images, scripts and inline styles. Markdown doesn't render. To show angle brackets, escape them as `&lt;` and `&gt;`, like the `&lt;your-host&gt;` in the examples.

### Image

- Use your official image, the one you build and publish, not a third-party rebuild.
- Include the registry in the name, like `ghcr.io/you/my-app:1`. Docker Hub images don't need one, so `you/my-app:1` is fine.
- Always set a tag, and pick one you'll keep publishing. A major version tag like `:1` is ideal, because people get fixes without surprise breaking changes. `:latest` works if that's what you publish. A tag for one exact release, like `:1.4.2`, goes stale unless you update the template every release.
- Build for `linux/amd64` and `linux/arm64` if you can. Loads of people run Portainer on a Raspberry Pi or another ARM box.
- Container templates only. For stacks, images go in the compose file.

### Ports

```json
"ports": ["8080:8080/tcp", "2222:22/tcp"]
```

- Each one is a string, in the form `host:container/protocol`.
- The container side must be the port your app listens on inside the container. The host side is just a default, and people can change it on the deploy form.
- Always include the protocol, `/tcp` or `/udp`. Portainer needs it to set up the mapping.
- Don't add a host IP, like `127.0.0.1:8080:8080/tcp`. Portainer's template format doesn't support it, and the deploy fails.
- Only publish what people need to reach. Metrics and internal ports can stay unpublished.
- Avoid 80 and 443 as host defaults, since a reverse proxy usually has them already.

### Volumes

```json
"volumes": [
  { "container": "/app/data" },
  { "container": "/media", "bind": "/srv/media", "readonly": true }
]
```

- `{ "container": "/app/data" }` makes Portainer create a new Docker volume for that path. Use this by default. It works on any host, and it doesn't need the bind mount permission that admins can take away from regular users.
- Add an entry for every path your app writes data to, like its database, config and uploads. Anything left out is lost whenever the container gets recreated, which happens on every update. Caches and temp folders can be skipped.
- If you can, keep all of your app's data under one folder, so a single volume covers it.
- Only use `bind` when people need to point the app at existing files on the host, like a media library. People can change the path on the deploy form. Add `"readonly": true` if the app only reads those files.

### Environment variables

Each entry becomes an input on the deploy form.

| Key | Type | What it does |
|-----|------|--------------|
| `name` | string | The variable's name. Required. |
| `label` | string | The input's label. Always set it, or people see the raw variable name. |
| `description` | string | A tooltip with more detail. |
| `default` | string | Pre-fills the input. |
| `preset` | boolean | When `true`, the `default` is applied and people can't change it. |
| `select` | list | Turns the input into a dropdown. Each option is `{ "text": "...", "value": "..." }`. Mark one with `"default": true`, or the dropdown looks set but sends a blank value. |

- Only list what most people will want to set on their first deploy, and link to your full list of options in the note.
- Give everything a working default, so the app starts without anyone touching the form.
- Values are always strings, like `"default": "8080"` and `"default": "true"`. Only `preset` and the `default` inside a `select` option are real booleans.
- Portainer passes every variable you list, even blank ones, so make sure your app treats an empty value the same as an unset one.
- For stacks, each variable here should appear as a `${VAR}` in your compose file, and each `${VAR}` people should be able to set should be listed here.

Secrets and passwords need a bit more care:

- Never ship a real default secret or password. Everyone who deploys the template would end up sharing it.
- Best of all, have your app generate what it needs on first start and save it to its data volume. Then the template needs no input.
- If people do have to provide one, leave out `default`, put "(required)" in the label, and say how to generate it in the description and the note. `openssl rand -hex 32` is a good suggestion, since hex is safe anywhere, even inside a URL. Portainer won't stop anyone deploying with it blank, so make your app refuse to start without it, or use `${VAR:?message}` in a stack's compose file.
- If your app creates an admin account from env vars, don't default the password to `changeme`. Make it required, or print a one-time password to the log on first start.

### Platform and restart policy

- `platform` is `linux` for almost every image, and Portainer shows it as an icon. Only use `windows` for Windows container images.
- `restart_policy` should be `unless-stopped` for anything long running. Without it Portainer uses `always`, which brings a container you'd stopped back up after a reboot.
- For stacks, set `restart:` in the compose file as well.

### Other fields

| Field | What it's for |
|-------|---------------|
| `command` | Overrides the image's default command, as one string. Better to build the right default into your image. |
| `privileged` | Gives the container full access to the host. Avoid it unless the app can't work without it. |
| `interactive` | Keeps a terminal attached, like `docker run -it`. Rarely needed. |
| `administrator_only` | Meant to hide the template from non-admin users, but current Portainer versions ignore it. Setting it to `true` on a template that needs host access does no harm, just don't rely on it. |

Leave these out:

- `id`, which the build assigns
- `labels`, `network` and `hostname`, since current Portainer versions ignore them when deploying a container template. For a stack, put them in the compose file.
- `registry`, since the registry goes in `image`
- `stackFile`, since stacks should point at your compose file with `repository`
- `maintainer`, which we fill in from `sources.csv`

## Getting the format right

- The file is plain JSON. No comments, and no trailing commas.
- It holds one template, as a single object like the examples.
- Portainer is strict about types. A number or boolean where it expects a string can stop it loading the entire template list, not just yours. Quote everything that's text, including numbers used as text like ports and defaults. Leave `true`, `false` and `type` unquoted.
- Spell field names exactly as shown here. Any field the build or Portainer doesn't recognise gets dropped without a warning, so a typo just quietly disappears. It's `restart_policy` not `restartPolicy`, `volumes` not `volume`, and `env` not `environment`.

## Security

A template runs with whatever access it asks for, on somebody else's server. Ask for only what the app needs.

- No secrets anywhere in the template or the compose file.
- No default passwords that stay valid after setup. See [secrets and passwords](#environment-variables) above.
- Only mount the Docker socket if the app works with containers. Even mounted read-only, the socket gives full control of Docker. If the app only needs to read, put a socket proxy like [`tecnativa/docker-socket-proxy`](https://github.com/Tecnativa/docker-socket-proxy) in front of it, the way [Homedex's compose file](https://github.com/HarshShah0203/homedex/blob/main/docker-compose.yml) does.
- Only use `privileged`, host networking, devices or extra capabilities when there's no other way, and explain why in the note.
- Portainer admins can block bind mounts, privileged mode and devices for regular users, so a template that needs them may only deploy for admins. Say so in the note.
- If the first person to open your setup page becomes the admin, say so in the note, so people finish setup before anyone else can reach it.

## Testing it

A template can pass every check and still not run, so test it three ways.

**1. Check the format.** Clone this repo and run the validator against your file's raw URL:

```bash
git clone https://github.com/lissy93/portainer-templates.git
cd portainer-templates
python3 -m venv .venv && . .venv/bin/activate
make install_requirements
python3 lib/validate_sources.py https://raw.githubusercontent.com/you/my-app/main/portainer-template.json
```

Fix every error, and the warnings too. The same check runs automatically on your PR.

Got Docker? Then you can go a step further and start it the way Portainer would, with the form left at its defaults. It waits for your app to come up and answer, and shows you its logs if it doesn't. A local file works here too:

```bash
python3 lib/test_template.py https://raw.githubusercontent.com/you/my-app/main/portainer-template.json
```

That one runs on your PR as well, as the 🧪 Test template check.

**2. For stacks, check the compose file on its own.** Set any required variables, then run:

```bash
docker compose -f docker-compose.yml config   # prints the file with every variable filled in
docker compose -f docker-compose.yml up -d
```

**3. Deploy it from Portainer.** This is the real test, since it's exactly what your users will do. Portainer reads a list of templates, so wrap yours in one and put it somewhere public, like a GitHub Gist:

```json
{
  "version": "3",
  "templates": [
    { "type": 1, "title": "My App", "...": "the rest of your template" }
  ]
}
```

In Portainer, go to Settings, paste the raw URL into the App Templates URL field and save. Then open your environment's app templates, find your app, and deploy it to a clean host, leaving the form at its defaults apart from any required secrets. Check that:

- every input on the form has a clear label and a sensible default
- it deploys, and the app opens on the expected port. Stacks deploy in the background, so check the stack's status in the Stacks list, not just the success message
- you can log in and actually use it
- your data survives. Add something, then recreate the container or redeploy the stack while keeping its volumes, and make sure it's still there
- it comes back by itself after the host restarts

When you're done, set the App Templates URL back to what it was, or to this project's list at `https://raw.githubusercontent.com/Lissy93/portainer-templates/main/templates.json`.

> [!TIP]
> Your `portainer-template.json` can use this wrapped format too, as long as it holds just one template. Then you can point Portainer straight at it while testing.

## Checklist

Go through this before you submit.

**It works**

- [ ] It deploys and starts with the default values. The only fields people must fill in are secrets that can't have a safe default, and those are clearly marked.
- [ ] I've deployed it from Portainer itself, on a clean host.
- [ ] The container ports match what the app actually listens on.
- [ ] Every path the app writes data to has a volume, and the data survives the container being recreated.
- [ ] It uses named volumes, with bind mounts only where people need to reach host files.
- [ ] Stacks only: the compose file is on the default branch of a public repo, uses published images and named volumes, and has a `${VAR}` for every variable in `env`.

**It's valid**

- [ ] `python3 lib/validate_sources.py <your URL>` passes with no errors or warnings.
- [ ] The file holds one template, with no `id`.
- [ ] Text values are quoted, and booleans aren't.

**It's unique**

- [ ] The app isn't already in the list under another name. If it's there already, I've used the same title and type so mine replaces it.
- [ ] The title is the app's real name.
- [ ] The logo is the app's own, square, at a stable URL.

**It's described well**

- [ ] The description is one or two plain text sentences, ending with `Source: https://github.com/you/my-app`.
- [ ] It has one to three existing categories.
- [ ] The note covers the port, the first login, any required secrets and where the data lives.
- [ ] Every env var has a label.

**It's safe**

- [ ] It uses the official image, with a tag I keep publishing, built for arm64 as well as amd64 where possible.
- [ ] There are no secrets or default passwords in the template or compose file.
- [ ] Docker socket access, privileged mode, host networking and devices are only there if the app can't work without them, and the note explains why.

## Submitting it

1. Commit `portainer-template.json` to your repo's default branch.
2. Add a row to the bottom of [`sources.csv`](../sources.csv), with a name, the raw URL of your file, your repo URL, and `app`:

   ```csv
   my_app, https://raw.githubusercontent.com/you/my-app/main/portainer-template.json, https://github.com/you/my-app/, app
   ```

   The name has to be unique, start with a lowercase letter or number, and only use lowercase letters, numbers, `_` and `-`.
3. If your app already has a copy in one of the files in [`sources/local/`](../sources/local), remove that entry in the same PR, along with any entry for it in [`overrides.json`](../overrides.json). Otherwise the old copy keeps winning and your updates never show up.
4. Open a PR here.

Once it's merged, you can edit the template in your own repo whenever you like, and changes show up here within a day. Keep the URL pointing at a branch rather than a tag or a commit.

Run the validator again after every change. If the file moves, stops being valid JSON, gains a second template or fails the checks, your app quietly drops out of the list until it's fixed, and nobody gets told.

Each app source holds one template. If you'd like to offer a second version, like a GPU build, publish it as a separate file with its own title, and add another row for it.

For anything else, like adding a whole list of templates, see the [contributing guide](CONTRIBUTING.md).
