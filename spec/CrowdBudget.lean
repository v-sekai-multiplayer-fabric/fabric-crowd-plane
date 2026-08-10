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

   The number of bodies a plane simulates is derived from the budget. It is never chosen.

   SUPERSEDED by the per-plane section below, and kept because it is the arithmetic the
   airlocks corrected. Everything here charges one plane for steering and contact across the
   whole venue. That is right for a venue held by one plane and wrong once a venue is rooms,
   because a plane then only pays for the people in its own room. Charging the full crowd
   overstated the fleet by half. The theorems still hold. They answer a question the design
   no longer asks. -/

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

theorem posing_a_venue_costs_a_sixth_of_a_core : venueUs * 100 / tickUs = 17 := by
  native_decide

/- ## A plane is one core, and a room is one plane

   Posing is cheap and it is not what a venue runs. A posed body does not fall over, does not
   get knocked down, and cannot be pushed through its own skeleton. That is the shape a
   social platform already has, so it is not worth building again. Every body here is
   physical.

   Physical bodies do not fit a venue on one core, and that is not the constraint anyway.
   The constraint is that a plane is one core. A venue is then as many rooms as it needs,
   one plane for each, joined by airlocks.

   An airlock is what makes this legal rather than a workaround. weft forbids a path that
   carries per-tick state between machines. An airlock carries none: two people in different
   rooms never share a contact neighbourhood, so there is nothing per-tick to carry. Somebody
   crossing is one actor migrating through the store plane, which is the slow durable path
   weft already has. A doorway takes a moment to walk through, and that moment is what hides
   the migration. The seam is diegetic.

   So the interesting quantity stopped being "how many cores does a venue need". It is "how
   many people fit one core", and a venue is that number times its rooms. -/

/-- Costs for one person for one frame, in nanoseconds. Nanoseconds because the smallest of
    them is 45, and microseconds would round it away.

    Every one of these was measured against a thousand-person crowd and divided down. They
    are per-person because a plane pays only for the people in its own room, which is the
    correction the airlocks force: charging every plane for the whole venue overstated the
    fleet by half. -/
def publishNsEach : Nat := joints * publishPsEach / 1000
def steerNsEach : Nat := steerUs * 1000 / people
def contactNsEach : Nat := contactUs * 1000 / people

/-- MEASURED. One tracked-avatar body under full forward dynamics, one step for each frame
    at a 16.7 millisecond timestep, in a batch of 28. This is the body that keeps its
    balance, falls over, and gets pushed. -/
def dynamicBodyNs : Nat := 29000

def perPersonNs : Nat := publishNsEach + steerNsEach + contactNsEach + dynamicBodyNs

theorem publish_is_45_ns : publishNsEach = 45 := by native_decide
theorem steer_is_280_ns : steerNsEach = 280 := by native_decide
theorem contact_is_2433_ns : contactNsEach = 2433 := by native_decide
theorem a_person_costs_31758_ns : perPersonNs = 31758 := by native_decide

/-- The body is 91 percent of a person. Everything else together is under a tenth, so there
    is no point tuning the other layers until the body moves. -/
theorem the_body_is_nine_tenths_of_a_person :
    dynamicBodyNs * 100 / perPersonNs = 91 := by native_decide

/-- THE ANSWER. One core, one plane, one room, 524 physical people.

    A plane is capped at one core by rule, so this is a capacity and not a target. -/
def peoplePerPlane : Nat := tickUs * 1000 / perPersonNs

theorem a_plane_holds_524 : peoplePerPlane = 524 := by native_decide

theorem a_plane_fits_its_core : peoplePerPlane * perPersonNs ≤ tickUs * 1000 := by
  native_decide

/-- One more person does not fit, which is what makes 524 the capacity rather than a guess. -/
theorem one_more_person_overruns :
    (peoplePerPlane + 1) * perPersonNs > tickUs * 1000 := by native_decide

/-- Rooms for a crowd, each room one plane on one core. -/
def roomsFor (crowd : Nat) : Nat := (crowd + peoplePerPlane - 1) / peoplePerPlane

theorem a_thousand_is_two_rooms : roomsFor people = 2 := by native_decide
theorem ten_thousand_is_twenty_rooms : roomsFor 10000 = 20 := by native_decide

/- ## Authority costs. Interest almost does not.

   524 is the number of bodies a plane can be the authority for. Authority is the single
   writer of an entity, so somebody pays the full 31758 nanoseconds for every person in the
   world exactly once.

   Interest is different in kind. A `CH_INTEREST` replica is read-only: the plane applies
   incoming joint entities and never integrates them. No contact solve, no constraint solve,
   no dynamics. It costs what it costs to write 36 numbers into a table.

   So the two are not variants of one thing to be traded off percentage by percentage. They
   are a hundred to one, and that ratio is the design. -/

/-- MEASURED. One core applying entity updates against a table too large for cache. This is
    the apply side, and it is a different measurement from the 1.25 nanosecond publish cost
    above, which is the write side. -/
def measuredAppliesPerSecond : Nat := 41200000

/-- weft measured one core applying 41.2 M entity updates each second against a table too
    large for cache, which is 24 nanoseconds for each. -/
def applyNsEach : Nat := 1000000000 / measuredAppliesPerSecond

/-- One interest replica, for one 60 Hz frame. Replicas arrive at the publish rate, so a body
    costs its 36 joints once every third frame. -/
def interestNsEach : Nat := joints * applyNsEach / ticksPerPublish

theorem an_apply_is_24_ns : applyNsEach = 24 := by native_decide
theorem a_replica_costs_288_ns : interestNsEach = 288 := by native_decide

/-- THE RATIO. One body a plane has authority over costs the same as a hundred it can merely
    see. Seeing is not the expensive part of a crowd, and it never was. -/
theorem one_authority_buys_a_hundred_replicas :
    perPersonNs / interestNsEach = 110 := by native_decide

/-- Replicas a plane can carry once its authority is set. -/
def replicasFor (authoritative : Nat) : Nat :=
  (tickUs * 1000 - authoritative * perPersonNs) / interestNsEach

/-- A plane that gives up a quarter of its authority sees the whole of a large venue.

    400 bodies simulated, 13000 more visible. The crowd a person looks at is 33 times the
    crowd their own plane is computing. -/
theorem four_hundred_authoritative_sees_thirteen_thousand :
    replicasFor 400 = 13759 := by native_decide

/-- Eight thousand people, twenty planes, everybody visible to everybody. Each plane has
    authority over 400 and holds replicas of the other 7600, and it still fits its core. -/
def bigVenue : Nat := 8000
def bigVenueAuthority : Nat := 400

theorem a_big_venue_is_twenty_planes :
    (bigVenue + bigVenueAuthority - 1) / bigVenueAuthority = 20 := by native_decide

theorem everybody_sees_everybody :
    bigVenueAuthority * perPersonNs + (bigVenue - bigVenueAuthority) * interestNsEach
      ≤ tickUs * 1000 := by native_decide

/-- It fills 89 percent of the tick, so this is the edge of the design and not a comfortable
    middle. -/
theorem the_big_venue_is_tight :
    (bigVenueAuthority * perPersonNs + (bigVenue - bigVenueAuthority) * interestNsEach) * 100
      / (tickUs * 1000) = 89 := by native_decide

/- One thing this does not buy, and it is the reason the airlocks stay.

   A replica is read-only and it is allowed to be stale. Somebody a person can see may be a
   frame or two behind and nothing is wrong. Somebody a person can touch may not be, because
   contact needs both bodies under one authority in one solve.

   So interest spans planes and contact does not. A person sees the whole venue and can push
   only the 400 on their own plane. The boundary has to fall where a crowd does not press
   against it, which is what an airlock or a low-density corridor is for.

   It also does not span machines cheaply. Two planes on one machine trade replicas over
   iceoryx2, zero copy. Two planes on different machines go through the store plane to
   FoundationDB, which is a global transaction measured in milliseconds. At a 50 millisecond
   publish period that is not obviously impossible, and it is not measured, so this section
   claims one machine only. -/

/- ## Cost

   Tenths of a cent, because the answer is 7.3 and a whole cent loses a third of it. The
   core-month price is the one weft already pays: thirty-two cores carrying a thousand people
   came to 122 cents for each head, which puts a core-month at 3812 cents. -/

def coreMonthCents : Nat := 3812
def tenthCentsPerHead (cores : Nat) : Nat := coreMonthCents * 10 * cores / people

/-- 121.9 cents, the musculoskeletal answer, for detail no tracker reports. -/
theorem musculoskeletal_costs_122_cents : tenthCentsPerHead 32 = 1219 := by native_decide

/-- The marginal cost of one more head, once a room is full: a core-month divided by the
    people on it. 7.2 tenths of a cent, and it does not depend on how large the venue is,
    because a larger venue is more rooms and not a fuller one. -/
def tenthCentsMarginal : Nat := coreMonthCents * 10 / peoplePerPlane

theorem a_head_costs_seven_tenths_of_a_cent : tenthCentsMarginal = 72 := by native_decide

/-- What a thousand people actually cost, which is two whole cores and not 1.9 of one. -/
theorem a_thousand_costs_76_tenths :
    tenthCentsPerHead (roomsFor people) = 76 := by native_decide

/-- Sixteen times cheaper than simulating muscles, with the same physical body behaviour:
    balance, falling, and being pushed. -/
theorem physical_bodies_cost_a_sixteenth :
    tenthCentsPerHead 32 / tenthCentsPerHead (roomsFor people) = 16 := by native_decide

/-- Four tenths of a cent was the target and this misses it. The gap is the price of physics.
    Posing hits 3.8 and cannot fall over, so the two are alternatives and not a trade to
    split. -/
theorem the_four_cent_target_is_missed : tenthCentsMarginal > 40 := by native_decide

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


def ringPercentOfCore (farJoints : Nat) : Nat :=
  ringPerSecond farJoints * 100 / measuredAppliesPerSecond

theorem full_skeletons_cost_one_percent_of_a_core : ringPercentOfCore joints = 1 := by
  native_decide

/-- Publishing every simulation tick instead of every third would triple it. -/
theorem publishing_every_tick_would_cost_five_percent :
    entities * simHz * 100 / measuredAppliesPerSecond = 5 := by native_decide

end Crowd
