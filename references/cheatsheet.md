# Arpent CLI Cheatsheet

Référence rapide des principales commandes de la CLI Arpent. `arp` est l'alias
court de `arpent`.

Cette fiche est opérationnelle mais non exhaustive. La syntaxe installée rendue
par `arpent <commande> --help` fait autorité.

## Quand la CLI est accessible

Le fichier `.arpent` sélectionne le mode du vault. La simple présence de la CLI
ne change pas ce mode.

| Contexte | Accès |
|---|---|
| Hors d'un vault | `--help`, `--version`, `skill install`, `init`, préparation d'un import, vérification/restauration d'un backup |
| Vault en mode `minimal` | Opérations direct-file; hors `--help` et `--version`, seules les commandes `init` et `mode` restent directement accessibles |
| Vault en mode `full` | Opérations CLI-mediated et état coordonné disponibles selon leurs autres prérequis |

Dans un vault minimal, toute autre commande est mode-gated. Si le marker contient
`auto_full: true`, la première commande concernée demande une promotion vers
`full`; sinon elle refuse de s'exécuter. La confirmation policy peut imposer
`arpent mode full --yes` avant de réessayer.

Le mode minimal ne signifie pas que le vault est inutilisable. L'agent peut
directement créer, lire, rechercher, router et archiver les fichiers canoniques.
Les opérations reposant sur SQLite, les transactions multi-fichiers, les index,
les imports appliqués, les sweeps et cron nécessitent le mode full.

### Confirmation et previews

- `--yes` fournit une confirmation lorsque la confirmation policy l'exige; ce
  n'est ni une permission de sécurité ni une preuve de revue humaine.
- `note new`, `note edit` et `todo add` peuvent retourner un `plan_sha256`.
  Réutiliser ce hash avec `--plan-hash` lie l'application au plan exact.
- `--dry-run` prépare ou prévisualise une opération sans mutation du domaine,
  mais des logs ou verrous locaux peuvent quand même être écrits.
- Pour cron, `--allow-local-code` active séparément l'exécution de code local;
  la confirmation policy peut aussi demander `--yes`.

Utiliser `arpent <commande> --help` pour la syntaxe exhaustive.

## Installation du skill agent

```bash
arpent skill install --to <répertoire-exact> [--replace] [--json]
```

Par défaut, la destination doit être absente. `--replace` demande explicitement
la mise à jour d'un répertoire existant : le nouveau bundle est préparé et
vérifié avant publication, et l'ancien est restauré si cette publication
échoue. Les fichiers ordinaires, symlinks et destinations non sûres restent
refusés.

## Initialisation et modes

| Commande | Usage |
|---|---|
| `arpent --version` | Afficher la version |
| `arpent init [path]` | Créer un vault full et initialiser Git |
| `arpent init [path] --minimal` | Créer le vault direct-file complet sans dépendance Git |
| `arpent init [path] --structure FILE` | Initialiser avec des Areas, Resources et projets déclarés |
| `arpent mode show [--json]` | Lire le mode sélectionné |
| `arpent mode full [--yes] [--json]` | Promouvoir vers le mode full et reconstruire les dérivés |
| `arpent mode minimal [--yes] [--json]` | Revenir au mode minimal sans supprimer l'état full |

## Vue d'ensemble, recherche et index

Ces commandes nécessitent un vault full.

| Commande | Usage |
|---|---|
| `arpent status` | Compter les notes par bucket et statut |
| `arpent triage [--json-page]` | Inventorier l'inbox, les âges, hashes et actions possibles |
| `arpent efforts [--json-page]` | Grouper les actionables actifs par cadence et effort |
| `arpent health [--json]` | Afficher les signaux de densité et de lifecycle |
| `arpent index [--yes]` | Reconstruire inventaire, recherche et contextes dérivés |
| `arpent search <query> [--json-page]` | Rechercher par mots-clés dans le vault |
| `arpent usage report [--since DATE] [--json]` | Résumer l'activité locale sans contenu sensible |

Les vues paginées acceptent généralement `--limit N`, `--cursor TOKEN` et
`--all`. `search` utilise automatiquement l'index courant ou un fallback live.

## Projets

```bash
arpent project create <name> \
  [--area SLUG] \
  [--effort-cadence heavylift|slowburn] \
  [--effort-level low|medium|high] \
  [--yes]
```

Full crée le projet, `_context.md`, `notes/`, `drafts/` et `attachments/` de
manière coordonnée. En minimal, créer la même structure directement depuis les
templates du vault.

## Notes

### Créer, lire et rechercher

```bash
arpent note new <title> [--type TYPE] [--status STATUS] \
  [--project SLUG] [--area SLUG] [--resource SLUG] \
  [--tags CSV] [--body TEXT | --stdin] \
  [--dry-run] [--json] [--plan-hash HASH]

arpent note read <id> [--json-page] [--full]
arpent note find <query> [--json-page]
```

Une note ordinaire conserve toujours les 27 clés du frontmatter canonique. Un
champ facultatif reste présent avec `null`, `[]` ou `false`; il n'est pas retiré.
Les types, IDs, dates, enums et relations sont validés. Une clé inconnue est
refusée plutôt que supprimée silencieusement. `appreciated` et `importance` sont
réservés à l'utilisateur et leurs valeurs existantes sont préservées. Les seuls
champs supplémentaires admis sont `archived_at` et `archived_from`, ensemble et
uniquement pour un événement d'archivage.

Capture fleeting implémentée:

```bash
arpent note new "<texte>" --type fleeting --json
```

Guide pratique global maintenu à jour après revue explicite:

```bash
arpent note new "<problématique précise>" --type howto \
  --source derived --body "<conclusion actuelle et liens>" --json
arpent note edit <howto-id> --body "<version revue>" --json
```

Un `howto` va dans `03_resources/how-tos/` avec `status: ongoing`; une MOC
reste une carte de navigation. Le détail et les conclusions remplacées restent
dans les notes liées.

### Modifier, router et archiver

```bash
arpent note edit <id> [champs et options --clear-*] \
  [--body TEXT | --stdin] [--dry-run] [--json] [--plan-hash HASH]

arpent note route <id> [--project SLUG] [--area SLUG] [--resource SLUG] [--yes]
arpent note status <id> <status> [--yes]
arpent archive <id> [--yes]
```

`note route` remplace les champs de routage. `archive` conserve l'historique et
refuse les IDs todo ou les sources linear qui ont leur propre lifecycle.
Statut et emplacement sont découplés: `note status ... archived` ne réalise pas
le déplacement trimestriel. `archived` est le statut; `archived_at` et
`archived_from` sont les métadonnées de l'événement d'archivage.

### Ingérer un fichier de l'inbox

```bash
arpent note ingest <00_inbox/path> --title <title> \
  [--type TYPE] [--project SLUG] [--area SLUG] [--resource SLUG] \
  [--attachment] [--source-hash SHA256] [--dry-run] [--json] [--yes]
```

Le texte est intégré sans perte. Un binaire reste intact et `--attachment` crée
une note Markdown compagnon.

### Notes linear

```bash
arpent note extract <linear-id> --type <type> --title <title> \
  [--project SLUG] [--area SLUG] [--resource SLUG] \
  [--body TEXT | --stdin] [--after EXACT_PASSAGE] [--yes]

arpent note dissolve <linear-id> [--yes]
```

`dissolve` exige au moins un enfant vérifié et archive la source linear.

## Import et migration

Les étapes de préparation peuvent être exécutées hors d'un vault. Dans un vault
minimal découvert, elles restent mode-gated et déclenchent une promotion ou un
refus. `apply` et `status` exigent un vault full.

```bash
arpent import scan <source> --output <plan> [--force] [--json]
arpent import suggest <plan> [--json]
arpent import review <plan> [--accept-suggestions] \
  [--minimum-confidence 0..1] [--yes] [--json]
arpent import validate <plan> [--sources] [--json]
arpent import summary <plan> [--json]
arpent import apply <plan> [--dry-run] [--yes] [--plan-hash HASH] \
  [--stop-on-error] [--json]
arpent import status <plan> [--json]
```

`scan` et `review` écrivent le plan, mais ne modifient pas les sources. `apply`
copie les éléments validés et conserve un état de reprise.

## Contextes et sessions

Les commandes `context` nécessitent le mode full et un `arpent index` préalable.

```bash
arpent context pending [--kind folder|note|text] [--path RELATIVE_PATH] \
  [--json-page]
arpent context show <path> [--level l0|l1|l2] [--json-page] [--full]
arpent context set <path> (--summary TEXT | --stdin) \
  --source-hash HASH [--provider ID] [--force] [--yes]
```

Clôturer une session en full:

```bash
arpent session end --summary <text> [--project SLUG] [--area SLUG] \
  [--decision TEXT ...] [--next-step TEXT ...] [--memory-log] [--yes]
```

Utiliser une cible projet ou area, sauf pour une écriture explicitement limitée
à `--memory-log`. En minimal, mettre à jour directement le `_context.md` cible.
Le log optionnel est absent par défaut et n'est jamais lu automatiquement. La
clôture de session ne ferme ni n'archive un projet.

## Todos

Toutes les commandes todo nécessitent le mode full et maintiennent ensemble
SQLite et leur trace Markdown.
Une action à exécuter ou suivre, y compris « rappelle-moi de faire X », est un
todo. Un buffer externe ne convient qu'à un contexte sans état d'exécution et
seulement avec un provider explicitement activé.

```bash
arpent todo add <content> [--priority KEY] [--status active|waiting|done] \
  [--due DATE] [--do DATE] [--project ID] [--depends-on ID] \
  [--dry-run] [--json] [--plan-hash HASH]

arpent todo list [--status active|waiting|done] [--include-archived] \
  [--json-page]
arpent todo show <id> [--json]
arpent todo edit <id> [champs et options --clear-*] [--yes]
arpent todo done <id> [--yes]
arpent todo defer <id> --to DATE [--yes]
arpent todo block <id> --on <object-id> [--yes]
arpent todo archive <id> [--yes]
```

Les dates sont en UTC au format `dd-MM-YYYY-HH-mm`. `todo archive` exige un todo
`done` et conserve sa ligne SQLite.

## Tools, lifecycle et cron

Ces familles nécessitent le mode full.

```bash
arpent tools list [--category VALUE] [--status VALUE]
arpent tools show <name>

arpent sweep ephemeral [--dry-run] [--yes]
arpent sweep status [--json]

arpent cron run --tick --dry-run
arpent cron run --tick --allow-local-code [--yes]
```

- `tools` inspecte seulement le registre; il ne change pas le statut des tools.
- `sweep ephemeral` traite uniquement les tools `ephemeral: true` avec
  `status: installed` et des règles déclarées.
- Cron n'est pas un daemon. Un scheduler externe doit appeler `--tick`.
- L'exécution cron est désactivée sur Windows; le dry-run reste disponible.
- Reader, review et z_backup restent `planned`/en construction et ne sont pas
  invocables. Le backup core ci-dessous est livré indépendamment de z_backup.

## Backups

```bash
arpent backup [--destination DIRECTORY] [--yes]
arpent backup verify <snapshot>
arpent backup restore <snapshot> --to <new-directory> [--yes]
```

La création exige un vault full. `verify` et `restore` peuvent être lancés hors
d'un vault; depuis un vault minimal découvert, ils restent mode-gated. La cible
de restauration ne doit pas déjà exister.
