#pragma once
// XRGridEntityPacket: the fabric's 100-byte entity packet.
//
// Not invented here. The source of truth is `lean-entity-packet`, whose Lean codec this
// mirrors field for field and whose `packet_golden.csv` the tests check against. The wire is
// fully integral so it models exactly in Lean, and a roundtrip property finds codec gaps
// without rebuilding an engine.
//
//   offset  field         encoding
//   0       gid           u32
//   4       pos x/y/z     int64 absolute micrometres
//   28      vel x/y/z     i16, scaled to V_MAX
//   34      (unused)      6 bytes
//   40      hlc           u32, (frame << 8) | counter
//   44      class|owner   u32
//   48      sub_index     u32
//   52      rot           i16 swing-twist x3, which is where a muscle travels
//   58      payload       42 bytes

#include <cstdint>
#include <cstring>

namespace crowd {

inline constexpr std::size_t kPacketSize = 100;
inline constexpr std::size_t kPayloadOffset = 58;
inline constexpr std::size_t kPayloadLen = kPacketSize - kPayloadOffset;

// The class field says how to read the packet. A skeleton joint derives its position from
// its parent and a static bone length, so its position field never changes and costs nothing
// once the stream is delta coded.
inline constexpr std::uint32_t kClassSkeletonJoint = 2;

#pragma pack(push, 1)
struct Packet {
  std::uint32_t gid;
  std::int64_t pos[3];
  std::int16_t vel[3];
  std::uint8_t unused[6];
  std::uint32_t hlc;
  std::uint32_t class_owner;
  std::uint32_t sub_index;
  std::int16_t rot[3];
  std::uint8_t payload[kPayloadLen];
};
#pragma pack(pop)

static_assert(sizeof(Packet) == kPacketSize, "the packet is 100 bytes, and the Lean says so");
static_assert(offsetof(Packet, pos) == 4, "position at 4");
static_assert(offsetof(Packet, vel) == 28, "velocity at 28");
static_assert(offsetof(Packet, hlc) == 40, "hlc at 40");
static_assert(offsetof(Packet, class_owner) == 44, "class and owner at 44");
static_assert(offsetof(Packet, sub_index) == 48, "sub index at 48");
static_assert(offsetof(Packet, rot) == 52, "rotation at 52");

}  // namespace crowd
