# fabric-crowd-plane

**We measured the budget but there is no simulator yet**

Simulate a thousand people in one venue at 60 Hz, published at 20 Hz, with one entity for
each joint.

weft's packet is 100 bytes with 6 bytes of rotation. It cannot describe a whole articulated
body. Split the body across entities and the packet fits with no change at all.

MS-Human-700 has 81 bodies, 85 joints, 85 degrees of freedom, and 700
actuators, and the 700 is muscles.
