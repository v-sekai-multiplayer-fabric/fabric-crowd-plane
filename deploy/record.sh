#!/usr/bin/env bash
# Record the crowd to an MKV, in two passes.
#
# Pass 1 captures the screen to a lossless intermediate (FFV1). Capture and encode are
# different jobs: a slow encoder that stalls the capture drops frames of the thing being
# recorded, and once dropped they are gone. FFV1 is fast enough to keep up and lossless, so
# the second pass has everything.
#
# Pass 2 burns the title and writes the metadata from CITATION.cff. AV1 because Fedora ships
# ffmpeg without x264.
#
# Recordings are artefacts. CLAUDE.md says not to commit them, so these land in ~/weft-videos.
set -euo pipefail

OUT="${1:-$HOME/weft-videos/weft-crowd-$(date +%Y%m%d-%H%M%S).mkv}"
# TikTok length. The platform accepts up to ten minutes and almost nobody watches past a
# minute, so the useful window is 15 to 60 seconds and this clamps to it. VERTICAL=1 crops to
# 9:16, which is what the feed shows full-bleed.
SECS="${SECS:-30}"
if [ "$SECS" -lt 15 ]; then SECS=15; fi
if [ "$SECS" -gt 60 ]; then SECS=60; fi
VERTICAL="${VERTICAL:-0}"
DISP="${DISPLAY:-:0}"
SIZE="${SIZE:-1440x900}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# --- from CITATION.cff -------------------------------------------------------
TITLE="weft — a crowd that touches"
AUTHOR="K. S. Ernest (iFire) Lee"
URL="https://github.com/v-sekai-multiplayer-fabric/weft"
DESC="Single-writer actors, a level-triggered pool reconciler, and durable per-actor SQLite for the multiplayer fabric control plane. Every body is physically simulated in one contact solve; only muscles cross the wire."
# CATSG terminology, which CITATION.cff adopts: Character, Avatar, Persona, Identity.
KEYWORDS="actors,control-plane,character,avatar,persona,identity,CATSG,Khronos,weft"

# drawtext reads these from files, so a colon in a URL is just a colon.
printf '%s' "$TITLE" > "$WORK/title.txt"
printf '%s  ·  %s' "$AUTHOR" "$URL" > "$WORK/by.txt"

# 9:16 for the feed: crop the middle of the capture, then scale to 1080x1920.
if [ "$VERTICAL" = "1" ]; then
  VFORMAT="-vf_unused"
  CROP="crop=ih*9/16:ih,scale=1080:1920,"
else
  CROP=""
fi
VFORMAT=""

FONT=$(find /usr/share/fonts -name "*.ttf" 2>/dev/null \
  | grep -viE '\[|\]' | grep -iE "dejavu.*sans.*bold|liberation.*sans.*bold" \
  | grep -viE "italic|oblique" | head -1)
[ -n "$FONT" ] && FONTOPT="fontfile=${FONT}:" || FONTOPT=""

# --- pass 1: lossless capture ------------------------------------------------
echo "capturing ${SECS}s from ${DISP} at ${SIZE}$([ "$VERTICAL" = 1 ] && echo ", vertical 9:16 out")"
ffmpeg -y -loglevel error \
  -f x11grab -framerate 30 -video_size "$SIZE" -i "$DISP" \
  -t "$SECS" -c:v ffv1 -level 3 -pix_fmt bgr0 "$WORK/raw.mkv"

# --- pass 2: title, then encode ---------------------------------------------
echo "encoding with title and metadata"
mkdir -p "$(dirname "$OUT")"
ffmpeg -y -loglevel error -i "$WORK/raw.mkv" \
  -vf "${CROP}drawbox=x=0:y=0:w=iw:h=132:color=black@0.62:t=fill:enable='lt(t,3)',\
drawtext=${FONTOPT}textfile=${WORK}/title.txt:x=40:y=30:fontsize=42:fontcolor=white:enable='lt(t,3)',\
drawtext=${FONTOPT}textfile=${WORK}/by.txt:x=40:y=90:fontsize=20:fontcolor=white@0.85:enable='lt(t,3)'" \
  ${VFORMAT} -c:v libsvtav1 -preset 8 -crf 32 -pix_fmt yuv420p \
  -metadata title="$TITLE" \
  -metadata artist="$AUTHOR" \
  -metadata author="$AUTHOR" \
  -metadata description="$DESC" \
  -metadata comment="$URL" \
  -metadata keywords="$KEYWORDS" \
  -metadata date="$(date +%Y-%m-%d)" \
  -metadata copyright="$AUTHOR" \
  "$OUT"

echo "wrote $OUT  ($(du -h "$OUT" | cut -f1))"
ffprobe -v error -show_entries format_tags -of default=noprint_wrappers=1 "$OUT"
