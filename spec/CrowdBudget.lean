/- The tick budget of the crowd plane, as arithmetic that is checked rather than asserted.

   Every number a reader would otherwise have to trust lives here as a theorem. When a
   measurement replaces an assumption, the constant changes and these either still hold or
   fail loudly, which is the whole reason the budget is not a comment.

   Writing it this way caught two arithmetic errors before any code existed: the tick is
   16666 microseconds and not 16667, and a rounding slip in the density ratio.

   Then the gate measurement caught two more, which is the better argument for the file.
   MS-Human-700 has 85 joints and not the 206 bones of a human skeleton, and one body costs
   4075 microseconds for a frame rather than the 500 assumed. Both numbers moved, both sets
   of theorems were rechecked, and nothing had to be remembered.

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

    MEASURED. MS-Human-700 reports 81 bodies, 85 joints, 85 degrees of freedom, 700
    actuators, and 700 tendons. The 700 is muscles, not joints. A human skeleton has 206
    bones, and that is a different count from the model's articulation. -/
def joints : Nat := 85

def entities : Nat := people * joints

theorem entities_is_85000 : entities = 85000 := by native_decide

/-- The densest thing weft has run is a recorded traffic trace. -/
def recordedPeak : Nat := 8637

theorem denser_than_the_recording : entities / recordedPeak = 9 := by native_decide

/- ## The tick budget

   Costs are in microseconds. The publish cost is derived from a measured marginal cost of
   1.25 nanoseconds for each entity, held in picoseconds so the division stays exact. -/

def publishPsEach : Nat := 1250
def publishUs : Nat := entities * publishPsEach / 1000000

/-- Assumed. Ten neighbours for each agent at 20 ns a pair. -/
def steerUs : Nat := 200

/-- Assumed, and the next thing to replace with a measurement. -/
def contactUs : Nat := 2000

/-- MEASURED. One MS-Human-700 body advanced through one 60 Hz frame on one core.
    509.4 microseconds for each `mj_step`, median of nine runs of two hundred, and the
    model's timestep is 2 milliseconds, so a frame is eight substeps. -/
def bodyFrameUs : Nat := 4075

def biomechUs : Nat := tickUs - publishUs - steerUs - contactUs

theorem publish_costs_106 : publishUs = 106 := by native_decide
theorem biomech_gets_14360 : biomechUs = 14360 := by native_decide

/-- The layers other than biomechanics fit the tick with room left. If this ever fails,
    the crowd cannot hold 60 Hz whatever the biomechanics costs. -/
theorem layers_fit : publishUs + steerUs + contactUs < tickUs := by native_decide

/- ## What the leftover buys

   The number of bodies a plane simulates is derived from the budget. It is never chosen. -/

def bodiesPerPlane (stepUs : Nat) : Nat := biomechUs / stepUs

def planesFor (stepUs : Nat) : Nat :=
  let n := bodiesPerPlane stepUs
  if n = 0 then people else (people + n - 1) / n

/-- THE ANSWER. Three bodies for each plane, at the measured cost. -/
theorem bodies_measured : bodiesPerPlane bodyFrameUs = 3 := by native_decide
theorem planes_measured : planesFor bodyFrameUs = 334 := by native_decide

/-- So biomechanics is a sample of the crowd and not the crowd. Three bodies in a thousand
    is the shape the measurement forces, and no amount of engineering in the other layers
    changes it. -/
theorem biomechanics_is_a_sample : bodiesPerPlane bodyFrameUs * 100 < people := by
  native_decide

/-- A body costing the whole tick leaves room for exactly one, which is the point at which
    the biomechanics layer stops being the crowd and becomes a sample of it. -/
theorem one_body_at_the_whole_tick : bodiesPerPlane biomechUs = 1 := by native_decide

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
theorem lod_24 : entitiesAtLod 24 = 28880 := by native_decide
theorem lod_8 : entitiesAtLod 8 = 14160 := by native_decide
theorem lod_root : entitiesAtLod 1 = 7720 := by native_decide

/-- Level of detail still pays, and less than it did at the assumed joint count: dropping
    distant bodies to the root cuts ring traffic elevenfold. -/
theorem lod_root_cuts_traffic_elevenfold : entities / entitiesAtLod 1 = 11 := by
  native_decide

/- ## The ring

   weft measured one core applying 41.2 M entity updates each second against a table too
   large for cache. Published at 20 Hz, a thousand full skeletons ask for a tenth of that. -/

def measuredAppliesPerSecond : Nat := 41200000

def ringPercentOfCore (farJoints : Nat) : Nat :=
  ringPerSecond farJoints * 100 / measuredAppliesPerSecond

theorem full_skeletons_cost_four_percent_of_a_core : ringPercentOfCore joints = 4 := by
  native_decide

/-- Publishing every simulation tick instead of every third would triple it. Splitting the
    two clocks is what keeps this cheap. -/
theorem publishing_every_tick_would_cost_twelve_percent :
    entities * simHz * 100 / measuredAppliesPerSecond = 12 := by native_decide

end Crowd
