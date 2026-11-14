// Easing and helpers. Every function is a pure function of time, so any frame renders alone.
export const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const inv = (a: number, b: number, x: number) => clamp((x - a) / (b - a));

// A cubic Bezier ease, the same curve as CSS cubic-bezier, solved by Newton's method.
export const bezier = (x1: number, y1: number, x2: number, y2: number) => {
  const cx = 3 * x1,
    bx = 3 * (x2 - x1) - cx,
    ax = 1 - cx - bx;
  const cy = 3 * y1,
    by = 3 * (y2 - y1) - cy,
    ay = 1 - cy - by;
  const sx = (t: number) => ((ax * t + bx) * t + cx) * t;
  const sy = (t: number) => ((ay * t + by) * t + cy) * t;
  const dx = (t: number) => (3 * ax * t + 2 * bx) * t + cx;
  return (x: number) => {
    x = clamp(x);
    let t = x;
    for (let i = 0; i < 8; i++) {
      const e = sx(t) - x;
      const d = dx(t);
      if (Math.abs(e) < 1e-6 || Math.abs(d) < 1e-6) break;
      t -= e / d;
    }
    return sy(clamp(t));
  };
};

export const E = {
  linear: (x: number) => clamp(x),
  // Soft at both ends: moves and the camera.
  standard: bezier(0.2, 0, 0, 1),
  // Entering: fast out, slow to stop.
  enter: bezier(0.05, 0.7, 0.1, 1),
  // Leaving: slow to start, fast away.
  exit: bezier(0.3, 0, 0.8, 0.15),
  // Smooth at both ends: fades.
  smooth: (x: number) => {
    x = clamp(x);
    return x * x * x * (x * (x * 6 - 15) + 10);
  },
  inOut: bezier(0.65, 0, 0.35, 1),
};

// A damped spring, solved exactly: drop, bounce once, settle. A smaller zeta bounces more.
// The default damping ratio 0.75 overshoots about 3%; positions may overshoot, opacity and
// color must not.
export const spring = (t: number, freq = 2.2, zeta = 0.75) => {
  if (t <= 0) return 0;
  const w = 2 * Math.PI * freq;
  const wd = w * Math.sqrt(1 - zeta * zeta);
  return 1 - Math.exp(-zeta * w * t) * (Math.cos(wd * t) + ((zeta * w) / wd) * Math.sin(wd * t));
};

// Progress of a motion starting at `at` and lasting `dur` seconds.
export const ramp = (t: number, at: number, dur: number, ease = E.standard) => ease(inv(at, at + dur, t));

// Visibility across an entrance, a hold and an exit.
export const life = (t: number, a: number, b: number, fin = 0.35, fout = 0.3) =>
  Math.min(E.smooth(inv(a, a + fin, t)), 1 - E.smooth(inv(b - fout, b, t)));

// Repeatable pseudo-randomness.
export const hash = (n: number) => {
  const s = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return s - Math.floor(s);
};
export const noise1 = (x: number, seed = 0) => {
  const i = Math.floor(x),
    f = x - i;
  const u = f * f * (3 - 2 * f);
  return lerp(hash(i + seed * 101), hash(i + 1 + seed * 101), u) * 2 - 1;
};

// The one used most: start moving at t0 and first arrive at t1, then overshoot slightly and
// settle. Set t1 to hit('keyword') and the motion lands on the keyword.
export const springTo = (t: number, t0: number, t1: number, zeta = 0.75) => {
  const dur = Math.max(1e-3, t1 - t0);
  const freq = (Math.PI - Math.acos(zeta)) / (2 * Math.PI * Math.sqrt(1 - zeta * zeta) * dur);
  return spring(t - t0, freq, zeta);
};
