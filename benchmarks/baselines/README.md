# Profile baselines

Snapshots produced by `python benchmarks/profile_vm.py --json`, kept so a later
run can be diffed against a known commit on a known platform.

These are observations, not targets. Machine, compiler and dispatch path all
move the numbers: the Windows build uses the portable `switch` dispatcher, Linux
and macOS use computed goto. Compare only like for like, and treat a move of
less than 10-15% as noise, especially for programs that finish in well under a
millisecond.

| file | platform | python | state |
| --- | --- | --- | --- |
| `windows-msvc-cp313.json` | Windows, MSVC 19.44, switch dispatch | 3.13 | after `e15e54f` |

A file is refreshed in place when the engine changes; the `commit` field says
which state it describes, and older snapshots stay in git history.

Regenerate:

```bash
python benchmarks/profile_vm.py --repeat 9 --warmup 2 --json benchmarks/baselines/<name>.json
```

Each file records the commit it was taken from and whether the working tree was
dirty, so a snapshot from a modified checkout is visible instead of silently
trusted.
