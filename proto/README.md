# The prototype, and where each piece runs

Two machines, and the split is the point. A layer on the wrong side of it is a layer that
proves nothing.

```
  PLAYER'S MACHINE                        DATACENTER
  ----------------                        ----------
  browser                                 crowd plane
    ^ renders from localhost                simulates every body, one contact solve
    |                                       writes the seqlock ring
  client.py                                     |
    Viser scene, local                          | iceoryx2
    decodes poses                               v
    sends stick input                       edge
        ^                                     terminates WebTransport
        |                                     hands frames to the plane
        +---------- WebTransport -------------+
```

**Viser runs on the player's machine.** It is a renderer, so it belongs where the player is.
Running it beside the physics would mean the datacenter is drawing pictures, which is the one
thing a plane must never do, and it would also hide the wire: if the poses never cross a
network, no wire format is being tested.

| file | runs on | what it is |
| --- | --- | --- |
| `plane.py` | datacenter | physics only. No rendering, no browser, no Viser. |
| `client.py` | the player's machine | Viser scene, decodes poses, sends input |

`plane.py` is Python and the design says the plane is C++. It is a stand-in, and `PLAN.md`
says what replaces it and why that matters. The split above is not a stand-in: it is the
shape the real thing has.
