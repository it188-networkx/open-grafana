# Fork PR checks

This fork uses standard GitHub-hosted Linux runners. The required `PR checks` gate waits for every planned job. Frontend changes run eight Jest shards, package and plugin suites, lint, type checks, and the production build. Backend changes run eight Go unit-test shards, four SQLite integration shards (only packages containing `TestIntegration*` tests), and compile all three server/CLI entry points. Existing short-mode unit tests and explicit SQLite integration suites follow the upstream split; other database variants and browser E2E suites are not part of this gate.

The planner classifies every changed path, including both sides of renames and deleted files:

| Changes | Required code checks |
| --- | --- |
| Root README/AGENTS/CI documentation; Markdown and images under docs/sources | None; policy tests and patch whitespace checks still run |
| public/, packages/, Yarn configuration, root package.json and frontend tool configuration | Frontend |
| pkg/, apps/, Go module/workspace dependency files | Backend |
| Shared schemas/API clients, dashboard migration definitions, CUE/Protobuf, generators | Both |
| CI policy, other scripts/configuration, unknown paths or manual full run | Both |

Shared contracts are classified before frontend/backend directories. Runtime Markdown/assets outside the documentation allowlist still trigger their code checks. No affected-package or affected-test shortcut is applied within a selected technology stack. This avoids missing indirect consumers and dynamic registrations. Failed, cancelled, or unexpectedly skipped jobs block merging. Repository rules require this gate before native automatic merge.

Upstream PR jobs depend on Grafana infrastructure, Enterprise source, or upstream organization credentials. They only handle PR events in grafana/grafana; their push, tag, dispatch, and release behavior is unchanged. The fork PR workflow needs no publishing or Enterprise credentials.

Use the checked-in Yarn version and the Go version from go.mod. `.actrc` runs the PR gate locally with Linux containers. The upstream commands remain available for targeted tests during development.

SQLite integration jobs reuse the upstream `pkgs-with-tests-named.sh -b TestIntegration` selector before applying four-way sharding. The previous command compiled every unit-test package even when the integration name filter matched nothing. Unit suites and server compilation remain separate required jobs. Policy regression tests cover scope boundaries, deletion/rename, failed/cancelled/skipped gates, and lossless integration-package partitioning.

The initial CI-changing PR intentionally runs both technology stacks. Compare cold and warm runs separately; an existing full-run baseline is 21m19s, with integration shard 4 spending 18m50s in package selection/compilation/testing. Documentation-only validation is not a full documentation site build or link checker.
