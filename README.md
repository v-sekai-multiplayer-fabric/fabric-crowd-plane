# fabric-crowd-plane

Simulate a thousand people in one venue at 60 Hz, published at 20 Hz, with one entity for
each joint.

State: the budget is proved but nothing is built.

Bodies touch, pressure builds at a doorway, and an arch forms
across a gap and holds. The flow through that gap does not follow from how many people want
through it. This plane simulates that, live.

weft's packet is 100 bytes with 6 bytes of rotation. It cannot describe a 206-joint body.
Split the body across entities and the packet fits with no change at all.

A thousand people is then 206000 entities.
