# How the crew works

## Ticket-first

Every task becomes a ticket before any work starts. Chat is for decisions; the board is for state.

```
queued → in_progress → review → done
              ↘ blocked ↗        ↘ requeue
```

A delivery counts only when **both** exist:

1. a written report (what was done, how it was verified, what is left), and
2. the ticket moved to `review` by the agent that did the work.

## Ownership

- The agent assigned to a ticket moves it. Nobody else moves it for them.
- Only the owner approves a ticket from `review` to `done`.
- Anything touching the host — install, deploy, new port, data migration — is proposed to the
  owner in one line and waits for an explicit yes.

## Verification

- Numbers come from a command, not from memory: the test total is quoted literally
  (`49 passed`), never "tests written".
- Infrastructure figures are re-measured at the time they are quoted.
- Claims about a UI are proven by opening it and reading the rendering, not by a health check.

## Communication

- Internal details (host, credentials, provider choice, cost) stay with the owner.
- Research ships with sources; anything unverified is labelled as such.
