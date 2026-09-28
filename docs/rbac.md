# RBAC

Two independent layers decide whether a request goes through. Both are enforced in
application code, not by the database (`backend/models/organization.py:10-13`).

## 1. Organization roles

Roles live on `Membership(organization_id, user_id, role)` (`backend/models/organization.py:24-30`).
A project belongs to one organization, and your role in that organization is your role in
every project under it — there are no per-project roles.

Ranked `owner > admin > member > viewer` (`backend/models/organization.py:10-13`).
`check_project_role(db, user_id, project_id, min_role)` (`backend/api/rbac.py:22-41`) returns
404 if the project doesn't exist, 403 if you aren't a member of its organization, and 403 if
your role ranks below `min_role`. `require_role(min_role)` (`backend/api/rbac.py:56-70`) wraps
it as a FastAPI dependency.

You become `owner` of an organization by creating it (`backend/api/organizations.py:29`); every
new account gets a personal organization + project on registration, also as `owner`
(`backend/services/organization_service.py:18`).

### What each role can do

| Minimum role | Actions | Checked at |
|---|---|---|
| any member | list org members, list org projects | `api/organizations.py:65`, `api/organizations.py:86` |
| `viewer` | read traces + trace stats, datasets + rows, prompts + versions, eval runs + live status, experiments; compare runs/experiments; analytics; list webhooks; Cohen's kappa | `api/traces.py:57,95,112`, `api/datasets.py:90,100`, `api/prompts.py:48,57`, `api/evals.py:56,70,83,117`, `api/experiments.py:60,69,94`, `api/analytics.py:18,30,37`, `api/webhooks.py:31`, `api/annotations.py:93` |
| `member` | ingest traces (SDK + OTLP), trace feedback, export traces to a dataset; create/upload/version/generate datasets; create/promote prompts, playground; start eval runs; create experiments, set baseline; assign annotations, export annotations | `api/traces.py:26,121,141`, `api/otlp.py:34`, `api/datasets.py:29,42,109,128`, `api/prompts.py:23,77,102`, `api/evals.py:32`, `api/experiments.py:41,78`, `api/annotations.py:33,103` |
| `admin` | create/delete webhooks (they call arbitrary URLs); invite members; create projects | `api/webhooks.py:20,40`, `api/organizations.py:46`, `api/organizations.py:74` |

Routes scoped to the caller rather than a project: your own annotation queue and submissions
(`api/annotations.py:53,61`) and your own API keys (`api/auth.py:46-73`).

### Not enforced (as of this writing)

- `owner` and `admin` are equivalent: no route requires `owner` specifically. The org/project
  delete that the model comment mentions (`models/organization.py:11`) has no endpoint.
- An `admin` can invite someone at any role, including `owner` — the invite route checks the
  caller is owner/admin (`api/organizations.py:46`), and the role validator only checks the
  value is one of the four roles (`schemas/organization.py:45-50`).
- There is no endpoint to change a member's role or remove a member.

## 2. API key scopes

Requests authenticated with a JWT (browser login) carry the account's full access. Requests
authenticated with an `oe_...` API key are additionally limited by the key's scope, before any
role check runs (`backend/api/deps.py:56-60`):

| Scope | Allowed |
|---|---|
| `read` | `GET` / `HEAD` only |
| `write` | any method, except `/api/auth/api-keys` |
| `admin` | everything, including creating/revoking API keys |

Scope narrows, never widens: a `write` key held by a `viewer` still gets 403 on every write,
because the role check in section 1 still applies.
