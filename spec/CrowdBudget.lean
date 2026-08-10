/- The tick budget of the crowd plane, as arithmetic that is checked rather than asserted.

   Every number a reader would otherwise have to trust lives here as a theorem. When a
   measurement replaces an assumption, the constant changes and these either still hold or
   fail loudly, which is the whole reason the budget is not a comment.

   Writing it this way caught two arithmetic errors before any code existed: the tick is
   16666 microseconds and not 16667, and a rounding slip in the density ratio.

   Then the measurements arrived and moved almost every constant in it, which is the better
   argument for the file. The joint count fell from an assumed 206 to a measured 36. The
   body cost went from 500 to 4075 to 950 to 433 as the model, the variant, the timestep,
   and finally the batch size were pinned down. Contact moved off one engine onto another.
   Steering came in 40 percent over its guess.

   The last of those moves is the one worth pausing on. The body did not get faster; the
   measurement got honest. A body measured alone costs 258 microseconds and a body measured
   in a full plane costs 433, and the first number was quoted for a while as though it were
   the second. A budget file cannot catch that on its own. It can only make the correction
   cheap once someone notices, which is what happened here.

   Every theorem was rechecked each time, and nobody had to remember which figures depended
   on which. Nothing in this file is assumed any more.

   Integers throughout. No Mathlib. Proofs are native_decide. -/
namespace Crowd

/- ## The two clocks -/

/-- Simulation. Steering, contact, and biomechanics all run at this rate. weft's
    `lib/weft/data_plane.ex` names 60 Hz for the game data plane. -/
def simHz : Nat := 60

/-- Publish. What reaches the ring and the bus, every third simulation tick. -/
def publishHz : Nat := 20

def tickUs : Nat := 1000000 / simHz
def ticksPerPublish : Nat := simHz / publishHz

theorem tick_is_16666 : tickUs = 16666 := by native_decide
theorem publish_every_third : ticksPerPublish = 3 := by native_decide

/- ## The crowd -/

def people : Nat := 1000

/-- A musculoskeletal human is not one entity carrying a pose. It is one entity for each
    joint, which is why weft's 100-byte packet fits unchanged: it never has to describe a
    whole body in its 6 bytes of rotation.

    MEASURED. The locomotion variant reports 81 bodies, 36 joints, 36 degrees of freedom,
    and 100 actuators. The full model is 85 joints and 700 actuators, and the 700 is
    muscles rather than joints. A crowd that walks does not need the hands or the face.
    A human skeleton has 206 bones, which is a different count again from either. -/
def joints : Nat := 36

def entities : Nat := people * joints

theorem entities_is_36000 : entities = 36000 := by native_decide

/-- The densest thing weft has run is a recorded traffic trace. -/
def recordedPeak : Nat := 8637

theorem denser_than_the_recording : entities / recordedPeak = 4 := by native_decide

/- ## The tick budget

   Costs are in microseconds. The publish cost is derived from a measured marginal cost of
   1.25 nanoseconds for each entity, held in picoseconds so the division stays exact. -/

def publishPsEach : Nat := 1250
def publishUs : Nat := entities * publishPsEach / 1000000

/-- MEASURED. `bench/bench_steering.cpp`, a thousand agents through a uniform grid, all
    walking at one doorway. 0.28 microseconds for each agent. -/
def steerUs : Nat := 280

/-- MEASURED. A thousand free capsules in one MuJoCo model, one step for each frame.

    Free capsules carry no muscle dynamics, so they need no 2 millisecond substep. Stepping
    them once for each frame instead of eight times is where this number comes from: the
    same crowd at a 2 millisecond timestep costs 15231 microseconds.

    They form a thousand separate islands, one for each body, and a thread pool does not
    help. At one contact each there is almost nothing to solve, and the time goes to
    collision detection and integration, which is straight-line work. 1, 4, 8, and 16
    threads all land within 4 percent of each other. -/
def contactUs : Nat := 2433

/- The musculoskeletal body, measured at scale. It is no longer the body a venue runs, but
   its numbers stay because they are what the cheaper body is measured against.

   One locomotion body alone advances a frame in 258 microseconds. The same body inside a
   batch of 28 costs 433. Nothing about the body changed. The models share one MjModel and
   each carries its own MjData, so what grew is the working set, and past about 14 bodies a
   core is waiting on memory rather than computing.

   A frame is two substeps at an 8 millisecond timestep. That timestep is the only tuning
   lever that moved anything: 2 ms costs 981 microseconds a frame, 4 ms costs 498, and 8 ms
   costs 255 for a single body. Driven at full muscle load for 10 simulated seconds, every
   one of those timesteps stayed stable and warned about nothing.

   Solver iterations are not a lever. 100, 50, 20, 10, and 5 iterations all cost the same to
   within a percent, because a body barely in contact has almost nothing to solve. -/

/-- MEASURED, and it is the constant that decides the fleet.

    A body sized to what an HMD and body tracking can observe. Six-point tracking reports
    head, two hands, waist, and two feet. Eleven-point adds elbows and knees. Nothing
    observes a muscle, a tendon, or a wrapping site, so this model carries none: 14 bodies,
    14 capsules, 0 sites, 0 tendons, 32 degrees of freedom, 26 torque actuators.

    It has almost the same degrees of freedom as the musculoskeletal body and costs a ninth
    as much, which locates the expense. A stage profile of the musculoskeletal body puts 81
    percent of a step in the position stage and 37 percent in forward kinematics alone. That
    is 81 bodies, 2856 sites, and 100 tendons through 430 wrap points, all transformed every
    step whether or not anything reads the muscle forces. Degrees of freedom were never the
    cost. Kinematic bulk was.

    This also holds flat under batching, where the musculoskeletal body does not: 48
    microseconds a frame at a batch of 1 and 52 at a batch of 128. The working set stays in
    cache, so the at-scale penalty that costs the musculoskeletal body 1.7 times does not
    arise. -/
def bodyFrameUs : Nat := 48

/-- The musculoskeletal body, kept as the second tier rather than deleted. It simulates what
    no tracker reports, so it is the right body for research and the wrong body for a
    venue. -/
def mskBodyFrameUs : Nat := 433

def biomechUs : Nat := tickUs - publishUs - steerUs - contactUs

theorem publish_costs_45 : publishUs = 45 := by native_decide
theorem biomech_gets_13908 : biomechUs = 13908 := by native_decide

/-- The layers other than biomechanics fit the tick with room left. If this ever fails,
    the crowd cannot hold 60 Hz whatever the biomechanics costs. -/
theorem layers_fit : publishUs + steerUs + contactUs < tickUs := by native_decide

/- ## What the leftover buys

   The number of bodies a plane simulates is derived from the budget. It is never chosen. -/

def bodiesPerPlane (stepUs : Nat) : Nat := biomechUs / stepUs

def planesFor (stepUs : Nat) : Nat :=
  let n := bodiesPerPlane stepUs
  if n = 0 then people else (people + n - 1) / n

/-- THE ANSWER. 289 tracked bodies for each plane, every figure in it measured. -/
theorem bodies_measured : bodiesPerPlane bodyFrameUs = 289 := by native_decide
theorem planes_measured : planesFor bodyFrameUs = 4 := by native_decide

/-- A thousand people fit four cores, so a venue fits one machine with room to spare. This
    is the theorem that retired the question of splitting a venue across machines. The
    question was never answered. It was dissolved, by a body that costs a ninth as much.

    weft forbids a path that carries per-tick state between machines, and
    `docs/essays/yagni.md` names the one thing that would reopen it: a measured workload
    that does not fit one machine. This measurement is the opposite of that. -/
theorem a_thousand_fits_one_machine : planesFor bodyFrameUs * 4 ≤ 16 := by native_decide

/-- Even a single core carries more than a quarter of the venue. -/
theorem one_core_carries_a_quarter : bodiesPerPlane bodyFrameUs * 4 > people := by
  native_decide

/-- The musculoskeletal body needs thirty-two planes for the same crowd, which is eight
    times the fleet for detail no tracker reports. -/
theorem msk_costs_eight_times_the_fleet :
    planesFor mskBodyFrameUs / planesFor bodyFrameUs = 8 := by native_decide

/-- The single-body cost would have promised 53 musculoskeletal bodies for each plane.
    Believing it would have sized the fleet at 0.6 of what the crowd needs, and the
    shortfall would only appear once a plane was full. -/
def singleBodyFrameUs : Nat := 258

theorem the_single_body_figure_overpromises :
    bodiesPerPlane singleBodyFrameUs = 53 := by native_decide

/-- A body costing the whole tick leaves room for exactly one, which is the point at which
    the biomechanics layer stops being the crowd and becomes a sample of it. -/
theorem one_body_at_the_whole_tick : bodiesPerPlane biomechUs = 1 := by native_decide

/- ## Posing beats simulating, when the pose is measured

   Forward dynamics answers "where does this body go". Tracking already answers it. Six
   trackers report head, two hands, waist, and two feet, and those six transforms determine
   the pose, so the limbs between them are solved rather than simulated.

   Each limb is a two-bone chain with one hinge, and a two-bone chain has a closed form. The
   law of cosines gives the elbow or knee angle and a swivel constant picks which way it
   points, which is the one thing tracking does not report. `bench/bench_pose.cpp` is the
   whole solver and it is about sixty lines. -/

/-- MEASURED. `bench/bench_pose.cpp`, a thousand tracked bodies on one core, every tracker
    moving every frame. 102 microseconds for the venue, 0.102 for each body.

    A general numerical solver is not an alternative. Damped least squares over six body
    jacobians, three iterations, costs 148 microseconds for ONE body: 1450 times the
    analytic cost, and 11 planes for the crowd instead of a fraction of one. The closed form
    is not an optimisation of the numerical route. It is a different route. -/
def poseVenueUs : Nat := 102

/-- Everything one venue costs on one core, at 60 Hz, with a thousand tracked people. -/
def venueUs : Nat := publishUs + steerUs + contactUs + poseVenueUs

theorem venue_costs_2860 : venueUs = 2860 := by native_decide

/-- THE ANSWER TO BOTH QUESTIONS. One core carries the whole venue, at 17 percent of a tick.

    The fleet is one core rather than thirty-two, so the cost for each head falls by the same
    factor. -/
theorem a_venue_fits_one_core : venueUs < tickUs := by native_decide

theorem a_venue_uses_a_sixth_of_a_core : venueUs * 100 / tickUs = 17 := by native_decide

/-- Cost for each head each month, in tenths of a cent. Tenths and not cents, because the
    answer is 3.8 cents and rounding it to a whole cent loses a fifth of it.

    The core-month price is the one weft already pays: thirty-two cores carrying a thousand
    people came to 122 cents for each head, which puts a core-month at 3812 cents. -/
def coreMonthCents : Nat := 3812
def tenthCentsPerHead (cores : Nat) : Nat := coreMonthCents * 10 * cores / people

/-- 121.9 cents, the musculoskeletal answer. -/
theorem musculoskeletal_costs_122_cents : tenthCentsPerHead 32 = 1219 := by native_decide

/-- 3.8 cents, the tracked answer, under the four-cent target. -/
theorem tracked_costs_under_four_cents : tenthCentsPerHead 1 = 38 := by native_decide
theorem tracked_is_under_the_target : tenthCentsPerHead 1 < 40 := by native_decide

/-- Thirty-two times cheaper, and the reason is not a faster body. It is a body that stopped
    computing what a tracker already reports. -/
theorem the_fleet_shrank_thirtyfold :
    tenthCentsPerHead 32 / tenthCentsPerHead 1 = 32 := by native_decide

/- ## What the leftover tick buys

   Posing the venue leaves most of the tick unspent, and forward dynamics is still there for
   whoever needs it. A body nobody is wearing has no tracker to pose it from, so an
   unattended body is simulated rather than posed. -/

def headroomUs : Nat := tickUs - venueUs

/-- MEASURED. One tracked-avatar body under full forward dynamics, one step for each frame
    at a 16.7 millisecond timestep, in a batch of 28. -/
def dynamicBodyFrameUs : Nat := 29

def dynamicBodiesInHeadroom : Nat := headroomUs / dynamicBodyFrameUs

/-- The same core that poses a thousand tracked people also simulates 476 unattended bodies
    outright. A venue does not have to choose between the two. -/
theorem headroom_carries_476_simulated : dynamicBodiesInHeadroom = 476 := by native_decide

/- ## The levers that are spent

   A constant this file cannot lower is worth recording, because the next reader will
   otherwise spend the same day rediscovering it. Each figure below is the at-scale cost of
   a body with something removed from it, in microseconds for each step. -/

def stepBaselineUs : Nat := 217
def stepNoMarginUs : Nat := 212
def stepNoMeshCollisionUs : Nat := 215
def stepNoContactUs : Nat := 199
def stepNoActuationUs : Nat := 210
def stepNoContactNoActuationUs : Nat := 193

/-- Only 19 geoms in the locomotion model collide: one plane, four meshes, and fourteen
    capsules. The other 330 are visual. So the mesh collision everyone reaches for first is
    worth about one percent, and swapping those meshes for primitives buys nothing. -/
theorem meshes_are_not_the_cost :
    (stepBaselineUs - stepNoMeshCollisionUs) * 100 / stepBaselineUs = 0 := by native_decide

/-- Deleting every contact in the model saves 8 percent. -/
theorem contact_is_eight_percent :
    (stepBaselineUs - stepNoContactUs) * 100 / stepBaselineUs = 8 := by native_decide

/-- Deleting the contacts and the hundred muscles together saves 11 percent. The 193
    microseconds left is smooth dynamics over 36 degrees of freedom, which is the part that
    cannot be removed while the thing stays a body. -/
theorem everything_removable_is_eleven_percent :
    (stepBaselineUs - stepNoContactNoActuationUs) * 100 / stepBaselineUs = 11 := by
  native_decide

/-- MJX, MuJoCo's JAX backend, on one CPU core. Batching does amortize, from 11509
    microseconds for each body at a batch of one down to 2177 at a batch of 64, but it
    starts so far behind that the asymptote never reaches the C engine. It is built to run
    thousands of environments on a GPU. It also needs the mesh margins zeroed before it will
    load this model at all, and about 25 seconds of compilation for each batch shape. -/
def mjxBestStepUs : Nat := 2177

theorem mjx_is_ten_times_slower : mjxBestStepUs / stepBaselineUs = 10 := by native_decide

/- ## Skeleton level of detail

   `lean-shared-core` puts the interest radius at 5 metres. A body outside it does not need
   206 joints. In a 20 by 20 metre venue at a thousand people, roughly 80 sit inside that
   radius of any one observer. -/

def nearBodies : Nat := 80
def farBodies : Nat := people - nearBodies

def entitiesAtLod (farJoints : Nat) : Nat := nearBodies * joints + farBodies * farJoints

/-- Entity updates each second at the publish rate. -/
def ringPerSecond (farJoints : Nat) : Nat := entitiesAtLod farJoints * publishHz

theorem lod_full : entitiesAtLod joints = entities := by native_decide
theorem lod_8 : entitiesAtLod 8 = 10240 := by native_decide
theorem lod_root : entitiesAtLod 1 = 3800 := by native_decide

/-- Level of detail still pays: dropping distant bodies to the root cuts ring traffic
    ninefold. -/
theorem lod_root_cuts_traffic_ninefold : entities / entitiesAtLod 1 = 9 := by native_decide

/- ## The ring

   weft measured one core applying 41.2 M entity updates each second against a table too
   large for cache. Published at 20 Hz, a thousand full skeletons ask for a tenth of that. -/

def measuredAppliesPerSecond : Nat := 41200000

def ringPercentOfCore (farJoints : Nat) : Nat :=
  ringPerSecond farJoints * 100 / measuredAppliesPerSecond

theorem full_skeletons_cost_one_percent_of_a_core : ringPercentOfCore joints = 1 := by
  native_decide

/-- Publishing every simulation tick instead of every third would triple it. -/
theorem publishing_every_tick_would_cost_five_percent :
    entities * simHz * 100 / measuredAppliesPerSecond = 5 := by native_decide

end Crowd
