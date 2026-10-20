# Fork PR checks

This fork uses standard GitHub-hosted Linux runners. The required `PR checks` gate waits for every planned job. Frontend changes run eight Jest shards, package and plugin suites, lint, type checks, and the production build. Backend changes run eight Go unit-test shards, four SQLite integration shards, and compile all three server/CLI entry points. Existing short-mode unit tests and explicit SQLite integration suites follow the upstream split; other database variants and browser E2E suites are not part of this gate.

Changes in shared configuration, scripts, dependencies, and unknown paths run both sides. Known root documentation changes skip expensive checks. Failed, cancelled, or unexpectedly skipped jobs block merging. Repository rules require this gate before native automatic merge.

Upstream PR jobs depend on Grafana infrastructure, Enterprise source, or upstream organization credentials. They only handle PR events in grafana/grafana; their push, tag, dispatch, and release behavior is unchanged. The fork PR workflow needs no publishing or Enterprise credentials.

Use the checked-in Yarn version and the Go version from go.mod. `.actrc` runs the PR gate locally with Linux containers. The upstream commands remain available for targeted tests during development.
