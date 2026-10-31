# Collig Personas

A public, reviewable market for **Collig personalities** — reusable dossiers that
make Collig speak and reason in the style of a person.

The market is deliberately data-only.  Adding a persona never adds executable
code to Collig.  Collig remains the place where a personality is created with
/distill; this repository is where finished dossiers are shared, reviewed and
installed.

## Install from Collig

Inside the Collig CLI or the web chat:

~~~text
/load-personas                 List the market (numbered)
/load-personas 2               Install entry 2
/load-personas 鲁迅             Install by slug, display name or alias
/load-personas search poet      Search names and aliases
/load-personas --all            Install everything
/load-personas --force 鲁迅      Replace an installed version
/load-personas refresh          Refresh the cached catalogue
~~~

After installing:

~~~text
/chatto 鲁迅
~~~

The catalogue is fetched from the main branch of this repository:

~~~text
https://raw.githubusercontent.com/cloudrevel-lab/collig-personas/main/index.json
~~~

Collig caches it under ~/.collig/personas-market/ and falls back to the cache
when GitHub is unreachable.

## Repository layout

~~~text
personas/
  <slug>/
    PERSONALITY.md     required; the dossier injected into the prompt
    meta.json          required; name, aliases, description, timestamps, sources
    sources.md         optional; reference notes
index.json             generated catalogue with SHA-256 file checksums
scripts/
  validate_personas.py validate data contract and secrets
  build_index.py       regenerate index.json
tests/
  test_personas.py     repository contract tests
~~~

A slug is the directory name and must match meta.json.slug.  It may contain
Unicode (for example 鲁迅), but no path separators, leading dot, control
characters or surrounding whitespace.

## Publish a persona

The supported workflow is from a Collig checkout:

~~~bash
make push-personas personality=~/.collig/personalities/鲁迅
~~~

That helper:

1. copies the local persona into a temporary clone of this repository;
2. runs the validator and the test suite;
3. regenerates index.json;
4. creates a branch, commits and opens a pull request with gh.

You need a GitHub login with write access and the GitHub CLI
(gh auth login).  A dry run is useful first:

~~~bash
uv run python scripts/push_persona.py --personality ~/.collig/personalities/鲁迅 --dry-run
~~~

You can also open a normal PR after manually adding personas/<slug>/.  The
GitHub Action runs the same checks as make test; a community reviewer should
check the dossier for quality, factual accuracy and safe content.

## First-time repository bootstrap

If the GitHub repository does not exist yet, an org maintainer can create it
from this checkout:

~~~bash
gh auth login
gh repo create cloudrevel-lab/collig-personas --public \
  --description "Reusable Collig personas"
git push -u origin main
~~~

After that, contributors only need make push-personas from a Collig checkout.

## Validation

~~~bash
make test              # validate + unit tests
make validate          # validate + require index.json to be current
make index             # regenerate index.json
~~~

Rules:

- only PERSONALITY.md, meta.json and sources.md are allowed inside a persona;
- no symlinks, no executable files, and a total size cap per persona;
- PERSONALITY.md must start with a level-1 heading;
- meta.json requires slug, name and updated_at;
- obvious credentials (OpenAI/GitHub/Slack/AWS keys, private keys) are rejected;
- index.json is generated from the persona files and their checksums; a stale
  index fails CI.

## Licence

Repository scripts and documentation: MIT.  Persona dossiers are contributed by
their authors and may quote public material; contributors are responsible for
having the right to share it.  See LICENSE and CONTRIBUTING.md.
