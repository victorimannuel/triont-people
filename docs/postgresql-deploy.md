# People by Triton PostgreSQL Notes

People is now ready to run against PostgreSQL through `DATABASE_URL`.

## Local PostgreSQL dev

Create the local role/database once:

```bash
./scripts/setup_local_postgres.sh
```

Default local credentials:

```text
DATABASE_URL=postgresql+psycopg2://people_app:people_dev_password@localhost:5432/people_dev
```

Run the app against local PostgreSQL:

```bash
./scripts/dev_postgres.sh
```

You can override names/passwords before setup:

```bash
PEOPLE_DB_NAME=people_dev PEOPLE_DB_USER=people_app PEOPLE_DB_PASSWORD='change-me' ./scripts/setup_local_postgres.sh
```

## Local Docker smoke test

```bash
cp .env.example .env
docker compose -f docker-compose.postgres.yml up --build
```

For a first production database, use the committed migrations instead of `db.create_all()`:

```bash
export FLASK_APP=app:create_app
export DATABASE_URL=postgresql+psycopg2://people_app:<password>@<host>:5432/people
export AUTO_CREATE_DB=false
flask db upgrade
```

Create new migrations only after model changes:

```bash
flask db migrate -m "describe change"
flask db upgrade
```

`AUTO_CREATE_DB=true` is only for fast local demos.

## ImeCo Ansible Fit

Current ImeCo infra pattern:

- app source is synced by an app role using `ansible.builtin.git`
- each app role templates its own `docker-compose.yml`
- services are under `{{ deploy_dir }}/services`
- apps are under `{{ deploy_dir }}/apps`
- secrets live in `inventories/group_vars/all/vault.yml`
- deploy-only flow is `ansible/playbooks/deploy-apps.yml`

Recommended People integration:

- add a shared `postgres` service role, separate from app roles
- add `people-by-triton` as an app role
- template People env values from vault
- run `flask db upgrade` as a one-off compose command during deploy
- expose People through the existing nginx role as another site template

Suggested vault vars:

```yaml
vault_people_secret_key: "long-random-secret"
vault_people_db_password: "strong-postgres-password"
```

Suggested public vars:

```yaml
people_domain: people.example.com
people_repo: https://github.com/<org>/<repo>.git
people_version: main
people_db_name: people
people_db_user: people_app
people_port: 8010
```

ImeCo infra cleanup before adding People:

- split app roles from shared service roles more consistently
- move per-domain nginx SSL lists into vars instead of hardcoded loops
- add a `postgres` role parallel to `mysql`
- make each app role produce the same outputs: source sync, env template, compose template, migrate command, start command
- keep app secrets in vault only; no passwords in compose templates
