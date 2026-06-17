# Contract Testing Methodology

How to verify that a feature works end-to-end by mapping the user journey, tracing it to functions, documenting contracts between them, and writing meaningful tests.

## Why This Exists

Testing individual functions in isolation proves nothing if you don't know whether you're testing the right thing. A function can pass all its unit tests and still be broken because:

- The caller passes different arguments than the test assumes
- The output format doesn't match what the consumer expects
- A branch in the journey was never tested
- The wire format between two systems has an undocumented constraint

This methodology forces you to start from the user's perspective and work inward, so every test is anchored to a real behavior.

## Step 1: Map the User Journey

Start from the user's first action and trace every step to the final visible result. Include ALL branches — not just the happy path.

**How to do it:**

1. Open the UI. Click the thing the user clicks. Write down what happens.
2. For each step, ask: "What else could happen here?" Document every branch.
3. Number every node. Use tree notation for branches:
   ```
   8.  POST /api/endpoint
   9.  ├─ 9A: Validation fails → error HTML
       ├─ 9B: Auth expired → redirect
       └─ 9C: Valid → continues
   ```
4. Follow parallel paths (background tasks, SSE streams, WebSockets) as separate tracks joined to the main journey.
5. Include lifecycle events: timeouts, reconnections, server restarts.

**The number at the end matters.** If you have 10 nodes and 2 branches, you haven't looked hard enough. A real user journey through a non-trivial feature has 20-40 nodes and 10-20 branches.

## Step 2: Trace Each Step to a Function

For every numbered node, identify:

- The **file and function** that handles it
- The **caller** (what invokes this function)
- The **consumer** (what uses this function's output)

This creates a chain. Every link in the chain is a contract.

## Step 3: Document Contracts

A contract is the agreement between a caller and a function. It has:

- **Input:** What the caller provides (types, valid ranges, edge cases)
- **Output:** What the function returns (type, structure, possible values)
- **Side effects:** What the function mutates (state, DOM, database, network)
- **Invariants:** What must always be true (e.g., "reassembled output == original input")

Write contracts as tables or structured text, not prose:

```
CONTRACT: _render_progress_html(progress_dict) → str

| Branch | Input              | Output                        |
|--------|--------------------|-------------------------------|
| 25A    | not active         | ""                            |
| 25B    | active, <2s        | ""                            |
| 25C    | active, >=2s, 1-99 | progress span (single line)   |
| 25D    | progress >= 100    | completion modal (multiline)  |
| 25E    | progress == -1     | error modal (multiline)       |

Invariant: 25D is NOT suppressed by the 2-second window.
```

**Every branch in the user journey must appear in a contract.** If a branch has no contract, it's untested.

## Step 4: Write Tests Against Contracts

Each test must:

1. **Name the contract it tests** — not "test_render_progress" but "CONTRACT 24, branch 25D: completion modal"
2. **Set up the exact input described in the contract** — not a convenient approximation
3. **Assert the exact output described in the contract** — not "contains some HTML" but "contains 'import-complete-modal' AND '64' AND 'outlook'"
4. **Test every branch** — if the contract has 5 branches, write 5 tests

**Count your assertions.** At the end, you should have:
- One assertion per contract branch
- One assertion per invariant
- One end-to-end assertion per parallel path

If `total_assertions < total_branches`, you missed something.

## Step 5: Test Across Boundaries

The hardest bugs live at boundaries between systems:

- **Python → SSE wire format → Browser JavaScript** — the SSE multiline newline bug lived here
- **HTMX response → DOM swap → JavaScript handler** — response format assumptions
- **Background task → shared memory → SSE poller** — timing and race conditions
- **Middleware → StreamingResponse → browser** — buffering kills SSE

For each boundary, ask: "What does the sender produce, and what does the receiver expect?" Then test that the sender's output matches the receiver's input format exactly.

**Example of a boundary test:**
```python
# Sender: _progress_stream yields SSE-encoded multiline HTML
# Receiver: EventSource reassembles data: lines with \n joins
# Test: reassembled output == original HTML

lines = html.split("\n")
sse = "".join(f"data: {line}\n" for line in lines) + "\n"
parts = [l[6:] for l in sse.split("\n") if l.startswith("data: ")]
reassembled = "\n".join(parts)
assert reassembled.strip() == html.strip()
```

## Step 6: Honest Code Audit

For each function in the chain, verify:

- **Pure functions** have no I/O, no side effects, no hidden state
- **I/O functions** are at the boundary, not in the middle
- **HTML** is in templates, not f-strings
- **State mutations** are explicit and documented in the contract
- **Error paths** surface errors to the user, never swallow silently

## Checklist

Before declaring a feature "tested":

- [ ] User journey mapped with numbered nodes
- [ ] All branches documented (happy path + every error/edge case)
- [ ] Total node count and branch count stated
- [ ] Every node traced to a file:function
- [ ] Contract documented for every function boundary
- [ ] Every contract branch has at least one assertion
- [ ] Boundary formats tested (sender output == receiver input)
- [ ] Total assertion count stated
- [ ] Honest Code audit completed
- [ ] End-to-end browser test confirms visible result
