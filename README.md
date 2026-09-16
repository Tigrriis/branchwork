# Villainy

Plan large, multi-stranded plots as a skill tree. A plot splits into
schemes (the columns), each scheme stacks its machinations in tiers, and every
machination carries points. A plain checkbox is a machination worth one point.

Formerly Branchwork. Only the words changed: the code, database tables, URLs,
static paths, the GitHub repo and the Render services all keep their original
names (`Project`, `Branch`, `Task`, `branchwork`), because renaming them would
break links and deployments for no one's benefit. The rest of this file uses
the code's names.

Above the trees sits the portfolio layer, built for someone who starts many
projects and forgets to move them along:

* **Today** splits your live projects into **Focus** and **Backburner** and
  lets you drag between them, so a weekend has a short deliberate list.
  Focus rows are full size with their next action and tempo; backburner rows
  recede and stop counting towards the "needs a touch" nagging. Focus is
  independent of phase: a project can be well into Building and still not be
  what you are touching this weekend.
* **Board** shows every project by status. Each account edits its own
  statuses under Account, Plot statuses: active ones are the columns, in
  the order Advance walks; a parked one is a shelf with a return date;
  closed ones are shelves for finished or abandoned work. Any active status
  can carry a cap, so a fourth build has to wait. New accounts start with
  Idea, Exploring, Building (capped at `WIP_BUILDING_LIMIT`), Maintaining,
  and Done, Parked and Dropped shelves. Plots store a status's key, which
  never changes, so renaming or reordering one moves nothing.
* **The sidebar** on every signed-in page switches between live projects:
  Focus, then Backburner, by name, with a dot on anything due and a count
  of ready routines. It folds to initials, opens on hover or with Ctrl K
  to filter, can be pinned open, and becomes a drawer on a phone.
* **Review** puts every active project on one scrolling page so the whole
  scope is visible at once, and takes one decision each: keep, advance, park
  or drop. Each card edits the project's objective and next action.
* **Inbox** captures ideas that belong to no project yet. Filing one sends
  it to that project's ideas, not into its tree; you can also park it until
  a date or tick it off.
* **Ideas** are the same thing scoped to one project, listed under its tree.
  They carry no points and count towards nothing until you drag one onto a
  tier, which is the moment it becomes a task. Dragging is the quick path;
  every idea also has a picker for touch and keyboard.
* **Activity** is recorded on every points change, task, phase move and
  review, and `flask sync-git` adds one event per commit for projects with a
  repository folder set. That feeds "last touched" and the 12-week strips.
* **Routines** are what a project needs doing on a tempo: invoices, a site
  walk, backups. They sit as a bar of abilities above the project's
  branches. Using one empties its icon, which refills over its tempo until
  it is ready again, and counts as a touch. Today's top bar gathers every
  ready routine from live projects, backburner included, because a
  routine's tempo is one you set on purpose.

**Templates** decide the branches a new project starts with. Five are built
in (Blank, Lifecycle, Engineering job, Software, Running business) and you
can copy any of them under Account → Project templates to get an editable
version: rename branches, change colours, set which ones wait on the one
before, and give each a few starting tasks (one per line, ` | 3` for the
points). Yours appear on the new-project form beside the built-ins.

Two rules give the tree its shape:

* **Tier gates.** Tier N opens once tier N-1 holds at least the project's
  gate points (default 3).
* **Branch locks.** A branch can wait on another branch and stays locked
  until that branch is complete.

Each tier fills with its branch's colour as its points add up, and is full
at exactly the gate points that open the tier below.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python bootstrap_db.py                 # creates instance/branchwork.db
.venv\Scripts\flask --app app seed-demo --email you@example.com --password yourpassword
.venv\Scripts\flask --app app run --debug
```

Then sign in at http://127.0.0.1:5000/login. `seed-demo` is optional; it
creates the "Office fit-out, Level 3" example from the design boards.

## Tests

```bash
.venv\Scripts\pytest
```

## Schema changes

Models live in `models.py`; migrations go through Alembic:

```bash
.venv\Scripts\flask --app app db migrate -m "describe the change"
.venv\Scripts\flask --app app db upgrade
```

`bootstrap_db.py` runs `upgrade` at boot and verifies the schema matches
the models, so a missed migration fails loudly rather than 500ing later.

## Deploy

The repository is a Render Blueprint. In the Render dashboard choose
**New → Blueprint**, pick `Tigrriis/branchwork`, and apply. Render reads
`render.yaml`, creates `branchwork-db` and the `branchwork` web service
together, generates `SECRET_KEY`, wires `DATABASE_URL` from the database,
and runs the migrations before gunicorn takes traffic. Later edits to
`render.yaml` re-sync on push.

Two free-tier limits worth knowing: a free Postgres instance is deleted 30
days after creation, and a free web service sleeps after 15 minutes idle.
Both are changed by switching plans in the dashboard; nothing in the code
depends on either.

The first account to register is just a normal account — there are no roles
and every project is private to its owner, so registration should be treated
as open to anyone who has the URL.

## Design

The chosen visual direction and the twelve explorations that led to it are
in `design/` (generated by the `gen*.mjs` scripts) and published as a
Claude Design canvas. `static/branchwork/theme.css` carries the tokens
lifted from the chosen board.

## Copy

Every word the app shows, including the product name, lives in one file:
`copy/villainy.toml`, grouped by the screen it appears on. Edit the text
between the quotes and reload; nothing else needs touching. Words in
`{braces}` are filled in by the app and must stay exactly as they are.

Templates read it through `t('key')`, Python through `tx("key")`, and the
browser's pop-ups through `window.COPY`. `tests/test_copy.py` fails if code
asks for a key the file lacks or the file holds a key nothing reads, and the
other tests assert through the catalogue, so rewriting copy never breaks them.

To edit in a browser instead, build the copy editor and publish it:

```bash
.venv\Scripts\python copy\export_editor.py
```

It saves each rewritten line to its own database. To write those back, export
the edits as JSON files into a folder and run:

```bash
.venv\Scripts\python copy\apply_edits.py path\to\edits
```

A line whose placeholders no longer match the original is refused and left
alone, and the catalogue is re-parsed before it is saved.

## Where graphical assets live

Split by whether a browser fetches the file:

* `static/branchwork/img/` — anything the app serves: the logo, favicons,
  illustrations. Everything under `static/` gets a content hash appended to
  its URL by `app._register_asset_versioning`, which is what makes the
  year-long cache lifetime safe, so a changed image reaches people at once.
* `design/` — masters and sources that are never served: the design boards,
  the generator scripts, editable originals.
* Neither — images uploaded at runtime. Render's filesystem is wiped on
  every redeploy, so those belong in the database or object storage.

Binaries stay in git history forever, so commit SVG and small PNGs freely
and keep large or layered originals out of the repo.

`img/logo.svg` is the mark, drawn bare in the header on the dark top bar.
Everything a browser tab or home screen shows is generated from it and
committed: `favicon.svg`, the PNG and ICO favicons, and the touch icon,
all with the mark on the app's dark ground so its white lines still show
on a light tab strip. This only runs when the logo changes:

```bash
npm install
node design/gen_icons.mjs
```

`design/logo1.af` is the Affinity source. Node is design-time tooling only;
the Flask app never touches it.

Machination icons are SVG files in `static/branchwork/img/machination_icons/`,
one per icon and named by the file (`bomb.svg` is `bomb`). Draw them in
white on a small square canvas: white is swapped for the colour of wherever
the icon sits, so a tile's icon still dims before it has points, and any
other colour stays as drawn. A new file shows up in the pickers without a
restart. The Affinity sources live in `design/machinations_icons/`.

## Keeping git activity honest

Set a project's repository folder on its edit page, then run this whenever
you like (a scheduled task works well):

```bash
.venv\Scripts\flask --app app sync-git
```

This reads git history from folders on the machine it runs on, so it always
runs locally even when the app itself is deployed. To point a local run at
the deployed database, copy the external connection string from the Render
dashboard and set it for that one command:

```bash
set DATABASE_URL=postgresql://...render.com/branchwork
.venv\Scripts\flask --app app sync-git
```

## Not yet

* Password reset (no email sending is wired up).
* Drag-and-drop reordering of tasks within a tier.
* Sharing a project with other users.
