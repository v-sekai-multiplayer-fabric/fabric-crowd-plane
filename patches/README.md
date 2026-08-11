# Patches to software this project does not own

A patch here is a change to an upstream checkout that weft depends on and cannot push to. It
lives in this repository so it survives the checkout being deleted, and so the next person
knows the dependency is modified.

## 0001, protomotions, bound the explicit PD slice

`protomotions/simulator/mujoco/simulator.py` recomputes explicit PD torques from

    q  = self.data.qpos[7:]
    qd = self.data.qvel[6:]

which runs to the end of the state rather than to the end of the humanoid. protomotions adds
five projectile bodies to the MJCF as free joints, so `qpos` carries 35 more entries than the
humanoid has, and the multiply against 66 gains fails:

    ValueError: operands could not be broadcast together with shapes (66,) (101,)

101 minus 66 is 35, which is five free joints of seven each. `_print_state_debug` in the same
file already bounds its slice the correct way, so the fix is to match it.

**This path crashes for anyone who runs explicit PD with projectiles enabled**, which is why
it was still there to find: nobody has run that combination.

Upstream is NVlabs/ProtoMotions. The change is kept on the local branch
`weft-mujoco-slice-fix` and as this patch.
