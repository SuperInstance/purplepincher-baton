# GitHub Runners as I2I Infrastructure

> The repo IS the shell. GitHub Actions IS the nervous system. Forks are the tide pool.

## Architecture

```
                    ┌─────────────────────────────┐
                    │    purplepincher-baton        │
                    │    (the shell / main repo)    │
                    │                               │
                    │  ┌─────────────────────────┐  │
                    │  │   GitHub Actions          │  │
                    │  │   (the nervous system)    │  │
                    │  │                           │  │
                    │  │  ┌───────┐  ┌──────────┐  │  │
                    │  │  │ On    │  │ On Fork   │  │  │
                    │  │  │ Push  │  │ PR from   │  │  │
                    │  │  │       │  │ proven    │  │  │
                    │  │  └───┬───┘  └─────┬────┘  │  │
                    │  │      │            │       │  │
                    │  │      ▼            ▼       │  │
                    │  │  ┌─────────────────────┐  │  │
                    │  │  │  Runner Agent        │  │  │
                    │  │  │  (PurplePincher)     │  │  │
                    │  │  │                      │  │  │
                    │  │  │  1. Load baton       │  │  │
                    │  │  │  2. Run task         │  │  │
                    │  │  │  3. File results     │  │  │
                    │  │  │  4. Update manuals   │  │  │
                    │  │  │  5. Sign guest book   │  │  │
                    │  │  └─────────────────────┘  │  │
                    │  └─────────────────────────┘  │
                    │                               │
                    │  ┌─────────────────────────┐  │
                    │  │  Summary Agent (cron)    │  │
                    │  │                          │  │
                    │  │  Watches all forks.      │  │
                    │  │  Docs what people are    │  │
                    │  │  doing with the shell.   │  │
                    │  └─────────────────────────┘  │
                    └─────────────────────────────┘
                          ▲           ▲
                          │           │
              ┌───────────┘           └───────────┐
              │                                   │
    ┌─────────┴──────────┐            ┌───────────┴──────────┐
    │  Trusted Agent     │            │  Zero-Trust Fork      │
    │  (SSH key deploy)  │            │  (anyone can fork)    │
    │                    │            │                       │
    │  Full runner       │            │  Runner checks fork   │
    │  access. Push      │            │  ONLY if contributor  │
    │  triggers full     │            │  has past worth-while │
    │  cycle.            │            │  commits. Not every   │
    │                    │            │  fork gets checked.   │
    └────────────────────┘            └───────────────────────┘
```

## Trust Tiers

### Tier 1: Trusted (Key-Based)
- Fleet agents (Oracle1, FM, JC1, CCC), Casey, Magnus
- Connected via SSH deploy keys
- Push → immediate build + test + file + sign
- All commits checked, all results filed

### Tier 2: Proven Contributors
- External contributors with past worth-while commits
- Their forks get runner attention (CI checks run)
- PRs auto-reviewed by summary agent
- Path to Tier 1: consistent good contributions → Casey grants key

### Tier 3: Unknown (Zero-Trust)
- Anyone can fork
- Runners do NOT check every fork automatically
- Summary agent scans fork activity periodically
- Interesting fork → elevated to Tier 2 review
- Safe by default: untrusted code never touches main without review

## The Runner Lifecycle

```yaml
# .github/workflows/purplepincher.yml
name: PurplePincher Shell Cycle

on:
  push:
    branches: [main]
  pull_request:
    types: [opened, synchronize]
  schedule:
    - cron: '0 */6 * * *'  # summary every 6 hours

jobs:
  check-trust:
    runs-on: ubuntu-latest
    outputs:
      tier: ${{ steps.trust.outputs.tier }}
    steps:
      - id: trust
        run: |
          if echo "$TRUSTED_KEYS" | grep -q "$ACTOR"; then
            echo "tier=1" >> $GITHUB_OUTPUT
          elif grep -q "$ACTOR" .shell/proven-contributors.txt; then
            echo "tier=2" >> $GITHUB_OUTPUT
          else
            echo "tier=3" >> $GITHUB_OUTPUT
          fi

  run-agent:
    needs: check-trust
    if: needs.check-trust.outputs.tier != '3'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Load baton
        run: cat baton/CONTEXT-REFERENCE.md
      - name: Run PurplePincher cycle
        run: python3 scripts/runner-cycle.py --tier $TIER
      - name: File results into manuals
        run: python3 scripts/file-to-room.py --batch results/*.json
      - name: Sign guest book
        run: |
          echo "### runner-$ID — $(date -u +%Y-%m-%d)" >> GUEST-BOOK.md
          git add -A && git commit -m "🤖 Runner cycle" && git push

  summarize:
    if: github.event_name == 'schedule'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Scan forks, generate digest
        run: python3 scripts/summary-agent.py --scan-forks --create-digest
      - name: File digest
        run: python3 scripts/file-to-room.py --room developers-manual --batch digest/*.json
```

## The Summary Agent

Runs on cron. Watches the ecosystem without checking every fork:

1. List all forks with recent activity
2. For each fork:
   - Proven contributor? → review their changes
   - Unknown but interesting? → flag for review
   - Spam / low quality? → ignore
3. Generate digest: "Here's what the community is doing with this shell"
4. File digest into developers-manual room
5. Update proven-contributors.txt if warranted

The summary agent reads commit messages, PR descriptions, diffs — NOT code execution. It documents what aspects of the shell people are exploring, without trusting any of the code.

## True I2I

- **Trusted agents** connect by keys → full runner → build, test, file, sign
- **Zero-trust** forks safely → runners check only proven ones → summary documents all
- **The shell evolves** from every direction — fleet, community, summary agents
- **No one waits** — trusted runs immediately, unknowns checked async
- **The guest book grows** — every cycle, every contributor, every improvement
- **The repo IS the shell. Runners ARE the nervous system. Forks ARE the tide pool.**
