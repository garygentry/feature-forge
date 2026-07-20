# Go Stack Profile

Stack-specific guidance for Go projects (1.21+).

## Stack Identity

- **Language**: Go 1.21+ (required for `slog` stdlib logging, `slices`/`maps` packages, improved generics)
- **Build system**: `go build`, `go install` (no external build tool required)
- **Module system**: Go modules (`go.mod` / `go.sum`)
- **Philosophy**: Simplicity-first — prefer the standard library, add dependencies only when justified

## Discovery Checklist

When examining a Go project, check for:

- **Module definition**: `go.mod` (module path, Go version, dependencies)
- **Dependency lock**: `go.sum` (checksums for reproducible builds)
- **Entry points**: `cmd/` directory (for CLIs, services, or multiple binaries)
- **Private packages**: `internal/` directory (compiler-enforced encapsulation)
- **Public packages**: `pkg/` directory (if used — not all projects follow this convention)
- **Build automation**: `Makefile`, `Taskfile.yml`, `mage` targets
- **Configuration**: `.golangci.yml` or `.golangci.yaml` (linter config)
- **Code generation**: `go generate` directives, `//go:generate` comments, `tools.go` for tool dependencies
- **Framework**: Check imports for chi, gin, echo, fiber (routers), or stdlib `net/http`
- **Database**: Check for sqlx, pgx, ent, gorm, or `database/sql`

## Archetype Conventions

### 00-core-definitions.md (Go)

- **Structs**: Use `struct` types with json/db tags (e.g., `` `json:"name" db:"name"` ``). Document every exported field with a comment.
- **Interfaces**: Keep small and behavior-focused (1–3 methods). Define at the consumer site, not the implementation site. Name with `-er` suffix where natural (e.g., `Reader`, `Validator`).
- **Error types**: Custom types implementing the `error` interface. Use `errors.New` for sentinel errors, `fmt.Errorf` with `%w` for wrapping. Group domain errors in a dedicated `errors.go` file.
- **Constants**: Use `iota` for sequential constants, typed constants for domain values, `const` blocks for related groups
- **Type aliases and generics**: Use sparingly. Generic types when the abstraction genuinely applies across multiple concrete types.
- **No barrel exports**: Go uses package-level visibility (`Exported` vs `unexported`); there is no index file pattern.

### 01-architecture-layout.md (Go)

- **Standard project layout**:
  - `cmd/<binary-name>/main.go` — entry points (one per binary)
  - `internal/` — private application code (compiler-enforced)
  - `pkg/` — public library code (optional, some projects skip this)
  - `api/` — OpenAPI specs, protobuf definitions, API contracts
  - `configs/` — configuration file templates
  - `scripts/` — build, install, analysis scripts
- **go.mod**: Module path matching the repo URL (e.g., `github.com/user/repo`), minimum Go version, direct and indirect dependencies
- **Package design**: One package per directory, package name matches directory name, package-level `doc.go` for documentation
- **Build considerations**: Cross-compilation with `GOOS`/`GOARCH`, build tags for platform-specific code, `ldflags` for version injection

### NN-testing-strategy.md (Go)

- **Framework**: `testing` package from stdlib (no external framework required)
- **Test file location**: `*_test.go` files in the same package (white-box) or `_test` package suffix (black-box)
- **Table-driven tests**: Standard pattern using slice of test structs with `t.Run()` subtests
- **Test helpers**: Functions accepting `testing.TB` with `t.Helper()` call at top
- **Mocking**: Interfaces + manual mocks, or testify/mock, gomock, mockgen if project uses them
- **Assertions**: stdlib `if got != want` pattern, or testify `assert`/`require` if project uses it
- **Integration tests**: Build tags (`//go:build integration`) to separate from unit tests
- **Benchmarks**: `func BenchmarkXxx(b *testing.B)` with `b.N` loop
- **Test fixtures**: `testdata/` directory (ignored by Go tooling), `TestMain` for setup/teardown

## Spec Quality Rules

- All Go code must be valid syntax with complete type information — not pseudocode
- Follow Go idioms:
  - Return `error` as the last return value — never panic for expected failures
  - Accept interfaces, return structs (depend on behavior, produce concrete types)
  - Design meaningful zero values (a zero-valued struct should be usable or clearly invalid)
  - No getters — use the field name directly (e.g., `user.Name` not `user.GetName()`)
  - Use embedding for composition, not inheritance
  - `context.Context` as the first parameter for any function that may block or be cancelled
  - `error` as the last return value for any function that can fail
- Include complete function signatures with named return values where they improve clarity
- Document every exported type, function, and method with a comment starting with the identifier name
- Use `//nolint` directives only with a justification comment

## Verification Specifics

- **Static analysis**: `go vet ./...` (catches common mistakes)
- **Linting**: `golangci-lint run` (if `.golangci.yml` exists or CI uses it)
- **Testing**: `go test ./...` (all packages)
- **Building**: `go build ./...` (ensures all packages compile)
- **Formatting**: `gofmt -l .` or `goimports -l .` (should produce no output)
- **Module tidiness**: `go mod tidy` (ensures `go.mod` and `go.sum` are consistent)

### Runtime Entrypoints & Bootstrap-Wiring Sites

Used by `CHECK-I22` (a runtime-required bootstrap needs a **non-test** caller on one of these) and
`CHECK-I23` (a heavy init wired into a **universal** bootstrap entry should move to a lazier site).

- **Runtime entrypoints (a legitimate non-test call site):** `func main()` in a `package main` under
  `cmd/…` or the module root, an HTTP handler registered on a `*http.ServeMux` / router, a gRPC service
  registration, or a worker/consumer goroutine started from `main` — not a `*_test.go` file.
- **Universal bootstrap entries (run on every startup — the `CHECK-I23` risk site):** a package-level
  `func init()` that constructs heavy clients, package-level `var` initializers that dial/connect at
  import time, or a single `bootstrap`/`wire` module `main` calls before serving. `init()` and
  package-var side effects run on **every** binary start, before `main` gets control.
- **Heavy server-only import markers (what makes an init "heavy" for `CHECK-I23`):** DB drivers/pools
  (`database/sql` + a driver, `pgx`, `gorm`, `mongo-driver`), message/queue clients (`sarama`/Kafka,
  `amqp`, `go-redis`), telemetry SDKs (`go.opentelemetry.io/*`, `sentry-go`), or a broad internal
  service package. An `init()` or package-var that dials any of these is the CHECK-I23 pattern —
  recommend a `sync.Once` lazy constructor invoked from the first handler that needs it, not an
  eager package-level connect.

## Testing

- **Framework**: `testing` stdlib package
- **Test command**: `go test ./...` for all, `go test -v -run TestName ./pkg/...` for specific
- **Table-driven tests**: Idiomatic pattern — slice of anonymous structs with `name`, input, and expected fields
- **Subtests**: `t.Run("case name", func(t *testing.T) { ... })` for grouped assertions
- **Assertions**: testify `assert`/`require` (if project uses it), otherwise manual `if` checks with `t.Errorf`
- **Coverage**: `go test -coverprofile=coverage.out ./...` then `go tool cover -html=coverage.out`
- **Race detection**: `go test -race ./...` for concurrency safety
- **Fuzzing**: `func FuzzXxx(f *testing.F)` (Go 1.18+)

## Common Frameworks

| Category | Options |
|----------|---------|
| HTTP router | net/http (stdlib), chi, gin, echo, fiber |
| Database | database/sql (stdlib), sqlx, pgx, ent, gorm |
| Migrations | golang-migrate, goose, atlas |
| CLI | cobra, urfave/cli, kong |
| Logging | log/slog (stdlib), zerolog, zap |
| Configuration | viper, envconfig, koanf |
| Dependency injection | wire, fx, dig |
| gRPC | google.golang.org/grpc, connect-go |
| Testing | testify, gomock, go-cmp |

## Example: Project-Level Override

Create `.feature-forge/stack-decisions.md` (legacy alias: `.claude/references/stack-decisions.md`) in your project root:

```markdown
# Stack Decisions

## Runtime & Build
- Go 1.22 with standard go toolchain
- Makefile for build automation

## Backend
- chi for HTTP routing
- sqlx with PostgreSQL
- log/slog for structured logging

## Testing
- testify for assertions and mocking
- Table-driven tests with t.Run() subtests
- Build tag `integration` for integration tests

## Conventions
- Standard project layout (cmd/, internal/, pkg/)
- golangci-lint with project .golangci.yml
- Context as first parameter, error as last return
- Interfaces defined at consumer site
```
