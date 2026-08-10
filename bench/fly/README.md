# Running the budget benchmarks on the platform

Every constant in `spec/CrowdBudget.lean` was first measured on a developer desktop. The
plane is sized from the body cost at the ninetieth percentile, so that one number decides
how many vCPU hold a thousand people. It is 1.7 times larger on Fly than on the desktop,
which cost the design a core.

Re-measure it like this. The machine is created, it runs once, and it is destroyed.

```sh
flyctl apps create weft-crowd-bench --org personal
flyctl deploy --build-only --push --image-label bench1
flyctl machine run registry.fly.io/weft-crowd-bench:bench1 \
  --app weft-crowd-bench --vm-size performance-2x --region sjc \
  --restart no --name bench-run1
flyctl logs --app weft-crowd-bench --no-tail        # the table, and a JSON line
flyctl machine list --app weft-crowd-bench          # take the ID
flyctl machine destroy <ID> --app weft-crowd-bench --force
```

## Leave nothing running

A run costs about a tenth of a cent, because the machine lives under a minute. An
undestroyed machine costs 83 dollars a month and breaks the cap on its own.

Check both after every run. An app with no machines and no volumes costs nothing.

```sh
flyctl machine list --app weft-crowd-bench
flyctl volumes list --app weft-crowd-bench
```

## Results

| host | median us/body/frame | p90 | vCPU for 1000 |
| --- | --- | --- | --- |
| Ryzen 7 3800X desktop | 27.3 | 31.4 | 3 |
| Fly performance-2x, sjc, AMD EPYC | 46.4 | 52.6 | 4 |
