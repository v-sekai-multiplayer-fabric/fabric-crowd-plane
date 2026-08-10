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

/- ### The fanout stops at the machine

   Interest is a fanout from the other simulating planes, and that fanout is shared memory.
   iceoryx2 does not cross a machine. Two planes on different machines go through the store
   plane to FoundationDB, which is a global transaction measured in milliseconds, so a
   50 millisecond publish period does not buy it back.

   The platform decides what that means, and the platform models a core as its own machine.
   A plane that is its own Fly app lands on its own machine, and then it has no neighbours to
   fan out from at all: it sees exactly the people it simulates.

   So mutual visibility is not free and it is not bought with tick budget. It is bought by
   putting several planes on one machine, on one Fly app with several vCPUs, sharing one
   /dev/shm. The venue that can see itself is therefore capped by the largest machine the
   platform sells, and not by anything in this file. -/

/-- Tenths of a cent for one core for one month. weft already pays it: thirty-two cores
    carrying a thousand people came to 122 cents for each head. -/
def coreMonthCents : Nat := 3812

/-- The vCPUs on the largest machine the platform offers. Not a tuning constant. It is a
    property of what can be bought, and the venue size follows from it. -/
def coresPerMachine : Nat := 16

/- ### More than one core for one plane

   A plane was one core because a plane is a thread-per-core harness and one core was enough.
   Give it two and the question is what actually gets faster.

   Bodies do. Each carries its own MjData and touches nothing else, so splitting them across
   threads is splitting independent work. Contact does not. A thousand capsules in one model
   was measured at 1, 4, 8, and 16 threads and all four landed within 4 percent of each
   other, so the contact layer is serial in practice whatever it is in principle.

   That makes contact the serial fraction, and it decides how far a plane is worth widening.
   It is 2433 nanoseconds of 31758, which is under a tenth, so two cores nearly double a
   plane and sixteen cores do not come close to multiplying it by sixteen. -/

def parallelNs : Nat := perPersonNs - contactNsEach

theorem the_serial_share_is_seven_percent :
    contactNsEach * 100 / perPersonNs = 7 := by native_decide

/-- People for one plane, given the cores it is given. Contact is paid once for each person
    whatever the core count. Everything else divides. -/
def peopleOn (cores : Nat) : Nat :=
  tickUs * 1000 / (contactNsEach + parallelNs / cores)

theorem one_core_holds_524 : peopleOn 1 = 524 := by native_decide
theorem two_cores_hold_974 : peopleOn 2 = 974 := by native_decide
theorem four_cores_hold_1706 : peopleOn 4 = 1706 := by native_decide
theorem sixteen_cores_hold_3907 : peopleOn 16 = 3907 := by native_decide

/-- Two cores are worth 1.85 planes, which is most of two. This is the reason to stop at two
    rather than at four. -/
theorem two_cores_scale_at_ninety_three_percent :
    peopleOn 2 * 100 / (peopleOn 1 * 2) = 92 := by native_decide

/-- Sixteen cores are worth 7.4 planes, so more than half of them are lost to the contact
    layer. Widening a plane has a knee and this is past it. -/
theorem sixteen_cores_scale_at_forty_six_percent :
    peopleOn 16 * 100 / (peopleOn 1 * 16) = 46 := by native_decide

/- ### The size of one contact neighbourhood

   This is what the extra core actually buys, and it is not throughput. Everyone on one plane
   is under one authority, so everyone on one plane can touch everyone else. The plane is the
   contact neighbourhood, so widening the plane widens the crowd that can press together.

   A thousand people who can all reach each other is the interesting venue, and two cores
   nearly reach it. Three cores pass it. -/

theorem three_cores_hold_a_thousand : peopleOn 3 > people := by native_decide
theorem two_cores_do_not : peopleOn 2 < people := by native_decide

/-- THE MACHINE FOR A THOUSAND. Three vCPUs, one plane, no fanout and no airlock, and every
    one of the thousand can touch every other. 8.4 tenths of a cent for each head each month.

    Two cores reach 974, which is close enough to be tempting and is not a thousand. The next
    size up the platform sells is what gets bought, so this is a four vCPU machine holding
    1706 with a third of it spare. -/
def thousandCores : Nat := 3

theorem three_cores_are_enough : peopleOn thousandCores ≥ people := by native_decide
theorem two_cores_are_not : peopleOn (thousandCores - 1) < people := by native_decide

/- ### Cores for each plane, once the fanout is in the budget

   Applying a replica is an independent write, so it divides across cores like the bodies do.
   Contact still does not. So the whole of a plane except contact scales, and the question is
   how to cut one machine into planes.

   Cutting it finely makes many small contact neighbourhoods. Cutting it coarsely makes few
   large ones. What is not obvious is what happens to the venue in between. -/

def planesOn (cores : Nat) : Nat := coresPerMachine / cores

/-- Authority for each plane, derived from its cores and how many planes share its machine.
    Contact is serial and everything else, replicas included, divides. -/
def sharedAuthority (cores : Nat) : Nat :=
  tickUs * 1000 /
    (contactNsEach + (parallelNs + (planesOn cores - 1) * interestNsEach) / cores)

/-- A venue that can see itself, which is one machine's worth of planes. -/
def visibleVenue (cores : Nat) : Nat := planesOn cores * sharedAuthority cores

theorem sixteen_planes_of_one : visibleVenue 1 = 7376 := by native_decide
theorem eight_planes_of_two : visibleVenue 2 = 7360 := by native_decide
theorem four_planes_of_four : visibleVenue 4 = 6676 := by native_decide
theorem one_plane_of_sixteen : visibleVenue 16 = 3907 := by native_decide

/-- THE REASON TO TAKE THE SECOND CORE. Two cores for each plane cost the same machine and
    show the same venue, to within a fifth of a percent, and double the crowd a person can
    actually touch. It is not a trade. Sixteen planes of one core is simply the worse cut. -/
theorem two_cores_show_the_same_venue :
    visibleVenue 2 * 1000 / visibleVenue 1 = 997 := by native_decide

theorem two_cores_double_the_contact_neighbourhood :
    sharedAuthority 2 / sharedAuthority 1 = 1
      ∧ sharedAuthority 2 * 100 / sharedAuthority 1 = 199 := by native_decide

/-- Past two the venue starts paying. Four cores for each plane shows nine percent fewer
    people, because four planes fan out to fewer neighbours than eight and the machine ends
    up carrying more authority than it has room for. -/
theorem four_cores_start_costing_the_venue :
    visibleVenue 4 * 100 / visibleVenue 1 = 90 := by native_decide

/-- The extreme: one plane holding the whole machine sees only what it simulates, and every
    one of those 3907 can touch every other. Nothing is stale anywhere. It is the smallest
    visible venue and the largest contact neighbourhood, which is the trade stated at both
    ends. -/
theorem one_big_plane_is_all_contact : visibleVenue 16 = sharedAuthority 16 := by native_decide

/-- Each plane fits its cores. -/
theorem the_visible_venue_fits :
    sharedAuthority 2 *
        (contactNsEach + (parallelNs + (planesOn 2 - 1) * interestNsEach) / 2)
      ≤ tickUs * 1000 := by native_decide

/- ### Scaling the machine up, and the thing that stops it

   vCPUs on one Fly machine share one /dev/shm, so planes on it trade replicas over iceoryx2
   and the venue grows with the machine. That is the direction to grow in, because growing
   sideways buys nothing: another machine cannot fan out to this one.

   Growing up has a shape, though, and it is not the shape it looks like. A plane replicating
   every other plane holds replicas in proportion to the plane count, and there are also that
   many planes, so the machine does work in proportion to the square of it. The venue still
   grows. The price for each head grows too, and eventually the replicas crowd out the
   bodies. -/

def venueAllToAll (machineCores : Nat) : Nat :=
  let planes := machineCores / 2
  planes * (tickUs * 1000 /
    (contactNsEach + (parallelNs + (planes - 1) * interestNsEach) / 2))

def costAllToAll (machineCores : Nat) : Nat :=
  coreMonthCents * 10 * machineCores / venueAllToAll machineCores

theorem all_to_all_16 : venueAllToAll 16 = 7360 ∧ costAllToAll 16 = 82 := by native_decide
theorem all_to_all_64 : venueAllToAll 64 = 24736 ∧ costAllToAll 64 = 98 := by native_decide
theorem all_to_all_256 : venueAllToAll 256 = 60288 ∧ costAllToAll 256 = 161 := by native_decide

/-- Sixteen times the machine buys eight times the venue, and each head costs twice as much.
    That is the quadratic showing up as a price. -/
theorem all_to_all_scales_sublinearly :
    venueAllToAll 256 * 100 / venueAllToAll 16 = 819 := by native_decide

theorem all_to_all_doubles_the_price :
    costAllToAll 256 * 100 / costAllToAll 16 = 196 := by native_decide

/- ### Culling by interest makes it linear

   A plane replicating every other plane is replicating people nobody on it can see.
   `lean-shared-core` puts the interest radius at 5 metres, and a plane holding one region of
   the venue needs only the band of the neighbouring regions that falls inside that radius.

   The size of that band is what matters, and the trap is to count it for each person. Eighty
   people stand within 5 metres of somebody, but the plane holds the union over everybody on
   it, not the sum. Those eighty are mostly the same eighty. What a plane replicates is a
   border, and a border grows with the edge of a region rather than its area.

   Written as a multiple of the plane's own authority, the border is the only term that
   matters, and the answer barely depends on it. -/

/-- Authority for each plane, when replicas are a border band `k` times its own authority. -/
def culledAuthority (k : Nat) : Nat :=
  tickUs * 1000 / (contactNsEach + (parallelNs + k * interestNsEach) / 2)

def venueCulled (k : Nat) (machineCores : Nat) : Nat :=
  machineCores / 2 * culledAuthority k

def costCulled (k : Nat) : Nat := coreMonthCents * 10 * 2 / culledAuthority k

/-- A border of one plane's worth, of two, of four. The price moves by two percent across
    all three, so the border does not have to be estimated well. -/
theorem a_border_of_one : culledAuthority 1 = 966 ∧ costCulled 1 = 78 := by native_decide
theorem a_border_of_two : culledAuthority 2 = 958 ∧ costCulled 2 = 79 := by native_decide
theorem a_border_of_four : culledAuthority 4 = 943 ∧ costCulled 4 = 80 := by native_decide

/-- THE POINT. The price for each head does not depend on the machine at all, because a plane
    replicates its neighbours and not the venue. Vertical scaling becomes linear. -/
theorem culled_cost_is_flat_in_machine_size :
    costCulled 2 = coreMonthCents * 10 * 16 / venueCulled 2 16
      ∧ costCulled 2 = coreMonthCents * 10 * 256 / venueCulled 2 256 := by native_decide

theorem culled_scales_linearly :
    venueCulled 2 256 * 16 = venueCulled 2 16 * 256 := by native_decide

theorem a_big_machine_holds_a_hundred_thousand :
    venueCulled 2 256 = 122624 := by native_decide

/-- Culling is already ahead at the smallest machine, and it is ahead by 2.6 times at the
    largest. Nothing about it is a large-venue optimisation. -/
theorem culling_wins_everywhere :
    venueCulled 2 16 > venueAllToAll 16
      ∧ venueCulled 2 256 * 10 / venueAllToAll 256 = 20 := by native_decide

/- ### What is still not bought, and why the airlocks stay

   A replica is read-only and it is allowed to be stale. Somebody a person can see may be a
   frame or two behind and nothing is wrong. Somebody a person can touch may not be, because
   contact needs both bodies under one authority in one solve.

   So interest spans planes on one machine, and contact never spans a plane at all. A person
   sees the whole machine and can push only the 400 on their own plane. That boundary has to
   fall where a crowd does not press against it, which is what an airlock or a low-density
   corridor is for.

   Past one machine there is no fanout, so a room on another machine is not dimmed or
   delayed. It is not there. An airlock between machines is opaque, and this is the one place
   where the constraint and the fiction agree without being made to: nobody expects to see
   through a door. -/

/- ### The two venues, and what each costs

   These are alternatives, and the choice is a deployment choice rather than a code one. -/

/-- An isolated room: one plane, its own machine, sees only itself. -/
def roomCost (cores : Nat) : Nat := coreMonthCents * 10 * cores / peopleOn cores

/-- A shared machine cut into planes, everybody visible to everybody. -/
def venueCost (cores : Nat) : Nat := coreMonthCents * 10 * coresPerMachine / visibleVenue cores

/-- An isolated room gets cheaper for each head the narrower its plane is, because contact is
    the serial part and a narrow plane pays less of it for each person. 7.2 tenths of a cent
    at one core, 7.8 at two, 8.9 at four. -/
theorem a_one_core_room_costs_72 : roomCost 1 = 72 := by native_decide
theorem a_two_core_room_costs_78 : roomCost 2 = 78 := by native_decide
theorem a_four_core_room_costs_89 : roomCost 4 = 89 := by native_decide

/-- A thousand people who can all touch each other: three vCPUs, 8.3 tenths of a cent for
    each head each month. -/
theorem a_thousand_costs_83 : roomCost thousandCores = 83 := by native_decide

/-- On a shared machine the cut at one core and the cut at two cost the same, to the tenth of
    a cent. So the second core is free and the contact neighbourhood it doubles is free with
    it. -/
theorem one_and_two_cores_cost_the_same : venueCost 1 = venueCost 2 := by native_decide
theorem a_shared_venue_costs_82 : venueCost 2 = 82 := by native_decide

/-- Cutting coarser is what costs. -/
theorem four_cores_cost_more : venueCost 4 = 91 := by native_decide
theorem sixteen_cores_cost_double : venueCost 16 = 156 := by native_decide

/-- Mutual visibility costs a seventh more for each head than an isolated room of the same
    shape. That is the price of the fanout, and it is paid in tick budget, not in cores. -/
theorem visibility_costs_a_seventh_more :
    venueCost 2 * 100 / roomCost 2 = 105 := by native_decide

/- ## Cost

   Tenths of a cent, because the answer is 7.3 and a whole cent loses a third of it. The
   core-month price is the one weft already pays: thirty-two cores carrying a thousand people
   came to 122 cents for each head, which puts a core-month at 3812 cents. -/

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

/- ## The topology for a touchable thousand, and what actually costs money

   A thousand who can all touch each other is one plane, so the topology question is what has
   to sit beside that plane rather than how to split it.

   Everything on the hot path shares one /dev/shm, because that is what iceoryx2 is. The edge
   terminates the transport and hands the decoded result to a plane over the bus. The BEAM
   reaches the ring through the NIF and never speaks iceoryx2. So the venue is one machine:

     crowd plane        3 vCPU   1365 capacity, 1000 used
     ring, NIF, BEAM    1 vCPU   control plane, placement, lifecycle
     edge               4 vCPU   HTTP/3 and WebTransport for a thousand clients
     ---------------------------------
     one machine        8 vCPU

   The store plane and FoundationDB are not on it. They talk over the network anyway, and
   they are shared across venues rather than sized for one.

   Then the arithmetic goes somewhere unexpected. -/

/-- weft's entity packet, from `lean-entity-packet`. -/
def packetBytes : Nat := 100

/-- What one client is sent each publish, at the level of detail the interest radius implies:
    the ten nearest bodies in full, and the seventy others as a root joint each. -/
def nearBodiesFull : Nat := 10
def farBodiesRoot : Nat := 70
def entitiesPerClient : Nat := nearBodiesFull * joints + farBodiesRoot

theorem a_client_gets_430_entities : entitiesPerClient = 430 := by native_decide

/-- Bytes each second, downstream, for one client. -/
def clientBytesPerSecond : Nat := entitiesPerClient * packetBytes * publishHz

theorem a_client_takes_860_kb_a_second : clientBytesPerSecond = 860000 := by native_decide

/-- 6.9 megabits, which is a video stream and not a control channel. -/
theorem a_client_takes_seven_megabits :
    clientBytesPerSecond * 8 / 1000000 = 6 := by native_decide

/-- The whole venue, downstream. -/
theorem the_venue_pushes_seven_gigabits :
    people * clientBytesPerSecond * 8 / 1000000000 = 6 := by native_decide

/- ### Egress costs more than the simulation, by a lot

   Tenths of a cent again. The platform bills egress by the gigabyte, and 2 cents is the list
   price for the regions this runs in. It varies, so it is a parameter and not a fact. -/

def egressTenthCentsPerGb : Nat := 20

/-- Gigabytes one head pulls in one hour of being present. -/
def gbPerHeadHour : Nat := clientBytesPerSecond * 3600 / 1000000000

theorem a_head_pulls_three_gigabytes_an_hour : gbPerHeadHour = 3 := by native_decide

/-- Tenths of a cent for one head for one hour of presence. -/
def egressTenthCentsPerHeadHour : Nat :=
  clientBytesPerSecond * 3600 * egressTenthCentsPerGb / 1000000000

theorem an_hour_of_presence_costs_61 : egressTenthCentsPerHeadHour = 61 := by native_decide

/-- The venue machine, eight vCPUs, for one month, spread over a thousand heads. -/
def machineCores : Nat := 8
def machineTenthCentsPerHead : Nat := coreMonthCents * 10 * machineCores / people

theorem the_machine_costs_304_for_each_head : machineTenthCentsPerHead = 304 := by
  native_decide

/-- THE FINDING. Five hours of presence in a month already costs more in egress than the
    entire machine costs for the month. Compute was never the expensive part of a crowd. -/
theorem five_hours_of_egress_beats_the_whole_machine :
    5 * egressTenthCentsPerHeadHour > machineTenthCentsPerHead := by native_decide

/-- At thirty hours in a month, which is an hour a day, egress is six times the machine. -/
def occupancyHours : Nat := 30
def egressTenthCentsPerHeadMonth : Nat := occupancyHours * egressTenthCentsPerHeadHour

theorem egress_is_six_times_the_machine :
    egressTenthCentsPerHeadMonth / machineTenthCentsPerHead = 6 := by native_decide

theorem a_head_costs_2_16_a_month :
    egressTenthCentsPerHeadMonth + machineTenthCentsPerHead = 2134 := by native_decide

/-- The crowd plane itself is three of the eight cores, and it is under a twentieth of the
    bill. Every hour spent making the body cheaper was spent on the small term. -/
theorem the_simulation_is_a_twentieth_of_the_bill :
    roomCost thousandCores * 100
      / (egressTenthCentsPerHeadMonth + machineTenthCentsPerHead) = 3 := by native_decide

/-- Which makes level of detail the lever that matters. Sending all eighty bodies in full
    would be 2880 entities rather than 430, and the bill would follow it. -/
theorem no_level_of_detail_costs_six_times_more :
    (80 * joints) / entitiesPerClient = 6 := by native_decide

/- ### The wire, once every trick is applied

   The 430-entity figure above sends a position and a rotation for every joint. A skeleton is
   not that. A joint's position is determined by its parent's rotation and a bone length that
   never changes, so the bone lengths go once at join time and every frame after that is
   rotations. One position for the root, and nothing else in the body needs one.

   That is the whole win, and it is structural rather than clever. Everything after it is
   small by comparison. -/

/-- Bits for each axis of a swing-twist rotation. 12 bits over a full turn is 0.09 degrees,
    which is finer than a tracker reports. 10 bits was measured too and costs a quarter less,
    at 0.35 degrees, which starts to show at the end of a long limb. -/
def rotBits : Nat := 12

/-- Bytes for one joint, bit-packed, three axes to a joint. -/
def jointBytes : Nat := (3 * rotBits + 7) / 8

/-- One body, packed: every joint as a rotation, plus one root position in micrometres. -/
def bodyPackedBytes : Nat := joints * jointBytes + 12

theorem a_packed_body_is_192_bytes : bodyPackedBytes = 192 := by native_decide

/-- MEASURED, and it is the NASTY protocol. weft has two wire formats and this is the
    hot-path one: bitpacked, cast to decode, never self-describing. The cheap CBOR JSON-LD
    format is the debug and interop edge and is costed below.

    `bench/wire.py` and `bench/wire_cheap_vs_nasty.py`, 300 to 400 frames of 16 bodies at a
    peak joint speed of 3 radians a second.

    The order of the pipeline decides the answer, which is the part worth remembering.
    Quantise, then delta, then zstd gives 127 bytes. Quantise, then pack, then zstd gives
    158, and giving zstd the previous frame as a dictionary gains nothing at all on top.
    Packing first destroys the delta: once three 12 bit fields are smeared across byte
    boundaries, consecutive frames no longer look alike to a compressor. So the bits get
    packed last or not at all.

    Compression on its own is nearly worthless here. zstd on the undifferenced packed form
    saves 9 percent, because quantised rotations are close to uniform noise. It is the delta
    that gives zstd something to find. -/
def nearBytesPerBodyFrame : Nat := 127

/- ### Muscle space, which is a better nasty than rotations

   A pose is not 36 joints times 3 axes. V-Sekai's `godot-humanoid-project` carries the
   Mecanim humanoid representation, and it has been in the organisation for years:
   `addons/humanoid/human_trait.gd`, Apache-2.0, Lyuma and lox9973. A pose there is 95 scalar
   muscles. Each one is a single axis of a single joint, normalised to [-1, 1] across an
   anatomical range that the file states outright in `MuscleDefaultMin` and
   `MuscleDefaultMax`. Dropping the fingers, the eyes, and the jaw leaves 49 for a body in a
   crowd.

   Two things follow, and the second is the one that was being left on the floor. There are
   fewer numbers: 49 against 108. And each number spans tens of degrees rather than a full
   turn, so the same angular precision costs fewer bits. A shoulder twist covering 200
   degrees needs 12 bits at 0.088 degrees. A jaw covering 20 degrees needs 9. The file
   already knows which is which, so the bit depth is read off the range and never chosen.

   This is what a nasty protocol is supposed to do. The range of motion is not data. It is a
   property of a human, it is the same for everybody, and it belongs in the schema rather
   than on the wire once every frame. -/

def bodyMuscles : Nat := 49

/-- MEASURED. `bench/wire_muscle.py`. Per-muscle bit depth from the anatomical range at
    0.088 degrees, which is the precision 12 bits gives over a full turn. 9 bits for the
    tightest muscle and 12 for the loosest, 511 bits for a body. -/
def musclePackedBytes : Nat := 76

/-- The rotation form, for comparison: 36 joints, 3 axes, 12 bits, plus a root. -/
def rotationPackedBytes : Nat := 174

theorem muscles_beat_rotations : rotationPackedBytes * 10 / musclePackedBytes = 22 := by
  native_decide

/- ### Entropy coding, and what run-length actually gives

   Muscle deltas are small, bounded, and heavily peaked at zero, which is the shape an
   entropy coder wants. Measured as an order-0 entropy over the delta symbols, which is the
   floor a range coder reaches to within a percent or two:

     packed, no coding                76 bytes
     packed then zstd                 83   <- WORSE than not compressing
     delta then zstd                  69
     entropy floor, absolute          63
     entropy floor, delta             53

   Two of those rows are worth stating out loud. Compressing the packed stream makes it
   bigger, because bit-packing at 9 to 12 bits smears every value across byte boundaries and
   a byte-oriented compressor sees noise. And the delta has to come before the packing, for
   the same reason.

   Run-length encoding was worth checking and is not worth having. 13 percent of muscle
   deltas are exactly zero, so the runs exist, but they are short and scattered. An entropy
   coder already spends about 3 bits on a symbol that common, and a run token cannot beat
   that without long runs to amortise it. Run-length is the right tool for a still crowd, and
   this crowd is in headsets and moving. -/

/- ### A long dictionary of previous frames does not pay

   MEASURED. `bench/wire_dict.py`, 600 frames of 16 bodies, four schemes over the same
   muscle-space deltas:

     independent frames               75 bytes   any loss is fine
     static trained dictionary        72         any loss is fine, 110 KiB shipped once
     keyframe every 20 frames         75         a loss costs a second
     keyframe every 60 frames         75         a loss costs three seconds
     streaming, full history          69         needs reliable ordered delivery
     order-0 entropy coder            53         any loss is fine

   Every dictionary scheme loses to the entropy coder, and the two that come closest are the
   two that demand the most from delivery. Keyframes gain nothing at all.

   The reason is worth keeping, because it decides the next format question too. A dictionary
   feeds LZ, and LZ finds repeated substrings. A bit-packed delta stream has none: two frames
   of a walk are similar in value and share no byte sequence, because the values sit at
   different offsets and are smeared across byte boundaries. There is nothing to match.

   What is left is redundancy in the symbol distribution, and that is exactly and only what
   an entropy coder takes. It is also why cheap CBOR compressed well earlier and nasty does
   not: CBOR repeats its key names every frame, so LZ has something to find. Compressing a
   good format looks disappointing, and that is the format working.

   This also settles the delivery question in the direction weft already wanted. The scheme
   that wins is stateless for each frame, so it rides sequenced unreliable WebTransport and a
   dropped datagram costs one frame rather than desynchronising a decoder. -/

/-- The design number: delta, then an order-0 range coder over the muscle symbols. 53 bytes
    plus a root position. zstd instead of a range coder gives 69 today and needs no new
    code, and no dictionary scheme beats it. -/
def muscleEntropyBytes : Nat := 53

def muscleStreamingBytes : Nat := 69
def muscleStaticDictBytes : Nat := 72
def muscleIndependentBytes : Nat := 75

/-- The entropy coder beats full-history streaming by 23 percent while needing none of what
    streaming needs. -/
theorem entropy_beats_streaming :
    (muscleStreamingBytes - muscleEntropyBytes) * 100 / muscleStreamingBytes = 23 := by
  native_decide

/-- A trained dictionary is worth 4 percent for 110 KiB shipped to every client. -/
theorem a_trained_dictionary_is_worth_four_percent :
    (muscleIndependentBytes - muscleStaticDictBytes) * 100 / muscleIndependentBytes = 4 := by
  native_decide

theorem the_wire_is_sixty_eight_times_smaller :
    joints * packetBytes * 100 / muscleEntropyBytes = 6792 := by native_decide

/-- The same skeletal frame as cheap CBOR JSON-LD: named joints, float rotations,
    self-describing. 1168 bytes raw, 884 with zstd and the previous frame as a dictionary. -/
def cheapBytesPerBodyFrame : Nat := 884

/-- Nasty is 7 times smaller than cheap here, and on the vehicle trace it was 2.3. The gap
    widens with the structure, because a self-describing format pays for every name and a
    body has 36 joints where a vehicle had 3 fields. So the choice between the two formats
    matters more for a crowd than it did for traffic, and it is the same choice. -/
theorem nasty_is_seven_times_smaller_than_cheap :
    cheapBytesPerBodyFrame / nearBytesPerBodyFrame = 6 := by native_decide

/-- Sending the crowd as cheap CBOR would put the venue back above two gigabits, which is
    where it was before the wire was looked at. The interop edge is not the hot path, and
    this is the arithmetic that says why. -/
theorem cheap_would_undo_the_whole_saving :
    people * (nearBodiesFull * cheapBytesPerBodyFrame * publishHz) * 8 / 1000000000 = 1 := by
  native_decide

/-- A body outside touching distance sends a root position and one rotation, and it sends
    them at 5 Hz rather than 20, because a client interpolates between them and nobody can
    tell at that distance. -/
def farBytesPerBodyFrame : Nat := 16
def farHz : Nat := 5

def clientBytesPerSecondPacked : Nat :=
  nearBodiesFull * nearBytesPerBodyFrame * publishHz + farBodiesRoot * farBytesPerBodyFrame * farHz

theorem the_packed_client_takes_31_kb : clientBytesPerSecondPacked = 31000 := by native_decide

/-- And in muscle space, with the far bodies down to a root position alone. -/
def clientBytesPerSecondMuscle : Nat :=
  nearBodiesFull * (muscleEntropyBytes + 12) * publishHz + farBodiesRoot * 12 * farHz

theorem the_muscle_client_takes_17_kb : clientBytesPerSecondMuscle = 17200 := by native_decide

theorem muscle_space_is_fifty_times_smaller_than_the_start :
    clientBytesPerSecond / clientBytesPerSecondMuscle = 50 := by native_decide

/-- A tenth of a megabit for each client, 137 megabits for the whole venue. -/
theorem the_venue_pushes_137_megabits :
    people * clientBytesPerSecondMuscle * 8 / 1000000 = 137 := by native_decide

/-- 27 times less than sending positions for every joint. -/
theorem packing_is_twenty_seven_times_smaller :
    clientBytesPerSecond / clientBytesPerSecondPacked = 27 := by native_decide

/-- A quarter of a megabit for each client, and a quarter of a gigabit for the venue. That is
    a control channel again rather than a video stream. -/
theorem a_client_takes_a_quarter_megabit :
    clientBytesPerSecondPacked * 8 / 1000000 = 0 := by native_decide

theorem the_venue_pushes_a_quarter_gigabit :
    people * clientBytesPerSecondPacked * 8 / 1000000 = 248 := by native_decide

/- ### Encoding once for each cell, not once for each client

   The other half of the ask is the pairwise part, and it does not move a single byte of
   egress. Every client needs its own bytes down its own connection, so nothing short of
   multicast changes that, and there is no multicast to the public internet.

   What it does move is the edge. Encoding for each client means 430 entities encoded a
   thousand times each frame. Encoding for each spatial cell means encoding a cell once and
   sending the same bytes to everybody subscribed to it. The bodies do not care who is
   watching, so the encode is shared and only the selection of cells is per client. -/

def cells : Nat := 20
def bodiesPerCell : Nat := people / cells

def encodesPerFramePerClient : Nat := people * entitiesPerClient
def encodesPerFramePerCell : Nat := cells * bodiesPerCell

theorem per_cell_encoding_is_430_times_less :
    encodesPerFramePerClient / encodesPerFramePerCell = 430 := by native_decide

/- ### The machine, and the bill, after all of it -/

/-- The edge no longer carries 6.9 gigabits, so it no longer needs four cores. Two. -/
def machineCoresPacked : Nat := 6

def machineTenthCentsPerHeadPacked : Nat := coreMonthCents * 10 * machineCoresPacked / people

def egressTenthCentsPerHeadHourPacked : Nat :=
  clientBytesPerSecondPacked * 3600 * egressTenthCentsPerGb / 1000000000

def egressTenthCentsPerHeadMonthPacked : Nat :=
  occupancyHours * clientBytesPerSecondPacked * 3600 * egressTenthCentsPerGb / 1000000000

/-- The bill in muscle space. -/
def egressTenthCentsPerHeadMonthMuscle : Nat :=
  occupancyHours * clientBytesPerSecondMuscle * 3600 * egressTenthCentsPerGb / 1000000000

theorem muscle_egress_is_37_a_month :
    egressTenthCentsPerHeadMonthMuscle = 37 := by native_decide

/-- 26.5 cents for each head each month, against 213 before the wire was looked at. -/
theorem a_muscle_head_costs_265 :
    machineTenthCentsPerHeadPacked + egressTenthCentsPerHeadMonthMuscle = 265 := by
  native_decide

/-- Egress is now an eighth of the bill, so the wire is finished and the machine is not. -/
theorem egress_is_now_an_eighth :
    egressTenthCentsPerHeadMonthMuscle * 100
      / (machineTenthCentsPerHeadPacked + egressTenthCentsPerHeadMonthMuscle) = 13 := by
  native_decide

theorem the_packed_machine_costs_228 : machineTenthCentsPerHeadPacked = 228 := by native_decide
theorem packed_egress_is_66_a_month : egressTenthCentsPerHeadMonthPacked = 66 := by native_decide

/-- 29.4 cents for each head each month, against 213 before the wire was looked at. -/
theorem a_packed_head_costs_294 :
    machineTenthCentsPerHeadPacked + egressTenthCentsPerHeadMonthPacked = 294 := by native_decide

theorem the_wire_saved_seven_times :
    (egressTenthCentsPerHeadMonth + machineTenthCentsPerHead)
      / (machineTenthCentsPerHeadPacked + egressTenthCentsPerHeadMonthPacked) = 7 := by
  native_decide

/-- And it hands the problem back to compute. Egress was 87 percent of the bill and is now
    22, so the machine is the term to attack next and the body work matters again. -/
theorem egress_is_now_a_fifth :
    egressTenthCentsPerHeadMonthPacked * 100
      / (machineTenthCentsPerHeadPacked + egressTenthCentsPerHeadMonthPacked) = 22 := by
  native_decide

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
