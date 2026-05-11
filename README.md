# shopsystem-test-harness

Harness Bounded Context of the **shopsystem** product. Per
[ADR-002](https://github.com/dstengle/shopsystem-product/blob/main/adr/002-harness-bc-introduction.md)
this BC sits in a self-introduced **Platform Operations** subdomain — it
serves the product itself rather than the product's end users.

## What it's for

Driving experiments and validating the shopsystem framework against
itself. The harness composes the three framework packages
(`shopsystem-messaging`, `shopsystem-scenarios`, `shopsystem-templates`)
at the CLI boundary (per prototype-1 finding 6) to spin up isolated
shop topologies, dispatch role templates against work items, capture
artifacts as evidence, and aggregate findings across runs.

## What it isn't

- **Not** a scaffolding tool for *production* shop creation. Standing up
  a real BC-shop for a consumer product is a separate concern.
- **Not** the inter-shop transport. Slices use the same `shop-msg`,
  `scenarios`, `shop-templates` surface as production work.
- **Not** a CI runner. The harness is invoked manually during framework
  development; CI can call it, but it has no opinion about CI.

## Ubiquitous language

- **experiment** — a named investigation with a target question.
- **slice** — a discrete unit of work within an experiment.
- **run** — one execution of a slice.
- **evidence** — frozen artifacts produced by a run (inboxes, outboxes,
  reports, before/after states).
- **finding** — a load-bearing claim emerging from one or more runs,
  with evidence pointers.
- **baseline** — a known-good state the harness validates against.

## CLI surface

The CLI binary is `shop-test-harness`. Subcommands are added as the
behavior gets pinned by scenarios. See `features/` for the current
contract.

## Dependencies

```
shopsystem-test-harness → shopsystem-messaging
                       → shopsystem-scenarios
                       → shopsystem-templates
```

All composition is at the CLI boundary.

## License

MIT. See [LICENSE](LICENSE).
