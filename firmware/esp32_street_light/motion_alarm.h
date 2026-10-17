#pragma once
#include <stdint.h>

// One window per LOW->HIGH transition. A held HIGH never restarts it.
class MotionAlarm {
 public:
  static constexpr uint32_t MAX_MS = 3000, COOLDOWN_MS = 10000;
  void update(bool motion, bool enabled, uint32_t now) {
    if (!enabled) { previous = motion; sounding = false; return; }
    if (motion && !previous && (!triggered || uint32_t(now - lastTrigger) >= COOLDOWN_MS)) {
      started = lastTrigger = now; triggered = sounding = true;
    }
    if (!motion || uint32_t(now - started) >= MAX_MS) sounding = false;
    previous = motion;
  }
  bool active() const { return sounding; }
 private:
  bool previous = false, triggered = false, sounding = false;
  uint32_t started = 0, lastTrigger = 0;
};

// Lower sound exposure: 60ms chirps, with 690ms of silence between them.
class QuietChirp {
 public:
  bool output(bool requested, uint32_t now) {
    if (requested && !previous) started = now;
    previous = requested;
    return requested && uint32_t(now - started) % 750 < 60;
  }
 private:
  bool previous = false;
  uint32_t started = 0;
};
