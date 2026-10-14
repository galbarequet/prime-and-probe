# Why a before/after probe *delta* can clean up the heatmap

> Status: **not implemented** on this branch. This note records the rationale so
> we can revisit it alongside the planned clock rework. Today `run_pp.c` records a
> single absolute `probe_time` per set.

## The problem with the absolute probe time

In the main loop we currently do, per repetition:

```
prime();                 // install the eviction set in every L1D set
victim(set, lines);      // the victim touches `lines` lines of one set
probe(result.probe);     // time re-traversing every set
```

and report `result.probe[set]` directly. Each set's measured time is

```
probe_time[set] = (true victim-induced eviction signal)
                + (per-set fixed offset)
                + (slow drift / noise)
```

The **per-set fixed offset** comes from things unrelated to the victim: phantom
self-eviction while priming, the set's position in the traversal order,
prefetcher state, and so on. Empirically this offset has a larger spread
(std ~11 ticks in older runs) than the victim ramp itself (~5 ticks across
0..NUM_LINES accessed). On the heatmap it shows up as **vertical banding** per
set that drowns the horizontal victim ramp we actually care about.

## The fix: measure each set against its own baseline

Probe **twice** per repetition — once right after `prime()` (a baseline, while
the set is still fully resident) and once after the victim runs — and report the
difference:

```
prime();
probe(before);           // baseline: set still fully primed
victim(set, lines);
probe(after);            // after the victim evicts
delta[set] = after[set] - before[set];
```

`before` and `after` share the same per-set fixed offset, so subtracting cancels
it and leaves (close to) just the victim-induced eviction signal. This also
mirrors how a real attacker thresholds each set against its own baseline rather
than against a global constant.

## Costs / trade-offs (why it's deferred, not free)

- **Wider prime -> victim window.** The extra `before` probe sits between prime
  and victim, giving the prefetcher/scheduler more time to perturb the primed
  sets. On a noisy clock this can add as much variance as it removes.
- **Roughly double the probe cost** per repetition and an extra column in the
  capture (`probe_before`, `probe_after`).
- **Needs an analysis-side switch.** `read_results.py` has to compute
  `after - before` (and ideally subtract each set's own `victim=0` row) instead
  of plotting the raw column.

## When to pick it up

Revisit together with the clock rework: the delta's benefit depends on the probe
being bracketed tightly enough that `before` and `after` really do share the same
offset. Once the finer clock lands, A/B the delta metric against the absolute one
on the same capture (emit both columns, switch the metric in `read_results.py`
without recompiling) and keep whichever gives the cleaner ramp.
