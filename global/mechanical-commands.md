When acting as a primary or orchestration agent, delegate mechanical commands to the
`luna-runner` subagent using the task tool.

Mechanical commands include:

- formatters such as `php-cs-fixer` and Prettier
- PHPUnit, Jest, and other test suites
- linters
- PHPStan and other type checks
- builds
- formatter and validation commands

Use the exact repository command and wait for the result when the parent task depends on it.

Run exploratory, Git, deployment, infrastructure, database, and failure-diagnosis commands
directly when they require the primary agent's context. Never delegate security-sensitive,
destructive, commit, reset, checkout, push, or deployment commands to `luna-runner`.
