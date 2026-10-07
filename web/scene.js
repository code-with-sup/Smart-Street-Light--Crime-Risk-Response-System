"use strict";
/* Illustrated night street with a working street lamp. Shared by the landing page and the dashboard.
   streetScene(id)            -> SVG markup
   setLamp(svg, level 0..1)   -> lamp brightness (light cone, pool, bulb)
   playStory(svg, onPhase)    -> landing-page loop: empty -> person (MEDIUM) -> knife (HIGH) -> clear */

function streetScene(id = "sc") {
  // Deterministic "random" windows so every render looks the same.
  let seed = 7;
  const rnd = () => ((seed = (seed * 9301 + 49297) % 233280) / 233280);
  const far = [];
  let x = -20;
  while (x < 1240) {
    const w = 50 + Math.floor(rnd() * 70), h = 120 + Math.floor(rnd() * 170);
    far.push(`<rect x="${x}" y="${400 - h}" width="${w}" height="${h}" fill="var(--scene-far)"/>`);
    for (let wy = 400 - h + 14; wy < 380; wy += 20) {
      for (let wx = x + 8; wx < x + w - 10; wx += 15) {
        if (rnd() < 0.16) far.push(`<rect x="${wx}" y="${wy}" width="7" height="9" fill="var(--scene-window)" opacity="${(0.35 + rnd() * 0.5).toFixed(2)}"/>`);
      }
    }
    x += w + 6 + Math.floor(rnd() * 14);
  }
  const stars = Array.from({ length: 40 }, () => `<circle cx="${Math.floor(rnd() * 1200)}" cy="${Math.floor(rnd() * 170)}" r="${(rnd() * 1.1 + 0.3).toFixed(1)}" fill="#fff" opacity="${(rnd() * 0.5 + 0.15).toFixed(2)}"/>`).join("");
  return `
  <svg class="scene" id="${id}" viewBox="0 0 1200 520" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
    <defs>
      <linearGradient id="${id}-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--scene-sky-top)"/><stop offset="1" stop-color="var(--scene-sky-bottom)"/></linearGradient>
      <radialGradient id="${id}-cone" cx="0.5" cy="0" r="1" fx="0.5" fy="0"><stop offset="0" stop-color="#FFD68A" stop-opacity="0.75"/><stop offset="0.55" stop-color="#FFB547" stop-opacity="0.18"/><stop offset="1" stop-color="#FFB547" stop-opacity="0"/></radialGradient>
      <radialGradient id="${id}-pool"><stop offset="0" stop-color="#FFC66E" stop-opacity="0.55"/><stop offset="1" stop-color="#FFC66E" stop-opacity="0"/></radialGradient>
      <radialGradient id="${id}-halo"><stop offset="0" stop-color="#FFE3A8" stop-opacity="0.9"/><stop offset="1" stop-color="#FFB547" stop-opacity="0"/></radialGradient>
    </defs>
    <rect width="1200" height="520" fill="url(#${id}-sky)"/>
    <g class="stars">${stars}</g>
    <g>${far.join("")}</g>
    <rect y="400" width="1200" height="120" fill="var(--scene-ground)"/>
    <rect y="398" width="1200" height="4" fill="var(--scene-curb)"/>
    <g fill="var(--scene-lane)">${Array.from({ length: 14 }, (_, i) => `<rect x="${i * 92 - 20}" y="476" width="46" height="4" rx="2"/>`).join("")}</g>
    <g class="lamp-light" style="opacity:0">
      <polygon points="508,152 562,152 800,402 270,402" fill="url(#${id}-cone)"/>
      <ellipse cx="535" cy="404" rx="300" ry="30" fill="url(#${id}-pool)"/>
      <circle cx="535" cy="150" r="46" fill="url(#${id}-halo)"/>
    </g>
    <g class="lamp-post">
      <rect x="402" y="142" width="9" height="260" rx="2" fill="var(--scene-pole)"/>
      <rect x="396" y="392" width="21" height="10" rx="2" fill="var(--scene-pole)"/>
      <path d="M406 146 C 430 116, 480 120, 520 138" stroke="var(--scene-pole)" stroke-width="7" fill="none" stroke-linecap="round"/>
      <path d="M500 132 L 570 132 L 562 150 L 508 150 Z" fill="var(--scene-head)"/>
      <rect class="lamp-bulb" x="511" y="148" width="48" height="5" rx="2.5" fill="#3A3833"/>
    </g>
    <g class="walker" style="opacity:0">
      <g class="walker-body" fill="var(--scene-person)">
        <circle cx="0" cy="-118" r="11"/>
        <path d="M-13 -103 Q 0 -108 13 -103 L 16 -52 L -16 -52 Z"/>
        <line class="leg-a" x1="-6" y1="-54" x2="-12" y2="0" stroke="var(--scene-person)" stroke-width="9" stroke-linecap="round"/>
        <line class="leg-b" x1="6" y1="-54" x2="12" y2="0" stroke="var(--scene-person)" stroke-width="9" stroke-linecap="round"/>
        <line class="arm" x1="-12" y1="-98" x2="-20" y2="-62" stroke="var(--scene-person)" stroke-width="7" stroke-linecap="round"/>
        <path class="blade" d="M-22 -64 L -38 -84 L -34 -86 L -19 -66 Z" fill="#D7DCE2" opacity="0"/>
      </g>
      <g class="det det-person" style="opacity:0">
        <rect x="-30" y="-136" width="60" height="140" fill="none" stroke="var(--det-person)" stroke-width="2"/>
        <rect x="-30" y="-152" width="92" height="16" fill="var(--det-person)"/>
        <text x="-26" y="-140" font-size="11" font-family="Geist Mono, monospace" fill="#081016" font-weight="600">PERSON 92%</text>
      </g>
      <g class="det det-knife" style="opacity:0">
        <rect x="-44" y="-92" width="30" height="32" fill="none" stroke="var(--det-weapon)" stroke-width="2.5"/>
        <rect x="-44" y="-108" width="78" height="16" fill="var(--det-weapon)"/>
        <text x="-40" y="-96" font-size="11" font-family="Geist Mono, monospace" fill="#fff" font-weight="600">KNIFE 81%</text>
      </g>
    </g>
  </svg>`;
}

function setLamp(svg, level) {
  if (!svg) return;
  const v = Math.max(0, Math.min(1, level));
  svg.querySelector(".lamp-light").style.opacity = v > 0 ? 0.15 + 0.85 * v : 0;
  svg.querySelector(".lamp-bulb").setAttribute("fill", v > 0 ? `rgba(255, 226, 160, ${0.45 + v * 0.55})` : "#3A3833");
}

const STORY = [
  // [start s, phase]
  [0, { level: "LOW", light: 20, buzzer: false, text: "Street clear · light dimmed to save energy" }],
  [3.2, { level: "MEDIUM", light: 100, buzzer: false, text: "Person detected at night · light to full" }],
  [7.0, { level: "MEDIUM", light: 100, buzzer: false, text: "Person lingering · looking around" }],
  [10.0, { level: "HIGH", light: 100, buzzer: true, text: "Knife detected · buzzer on · snapshot saved" }],
  [13.6, { level: "MEDIUM", light: 100, buzzer: false, text: "Weapon gone · light held while person leaves" }],
  [16.2, { level: "LOW", light: 20, buzzer: false, text: "Street clear · light dimmed to save energy" }],
];
const STORY_LENGTH = 18;

function playStory(svg, onPhase) {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const walker = svg.querySelector(".walker");
  const legA = svg.querySelector(".leg-a"), legB = svg.querySelector(".leg-b");
  const detP = svg.querySelector(".det-person"), detK = svg.querySelector(".det-knife"), blade = svg.querySelector(".blade");
  let lamp = 0.2, current = -1, start = performance.now(), visible = true;
  // pause while scrolled away; with reduced motion show one still of the HIGH moment
  new IntersectionObserver(([entry]) => {
    const wasHidden = !visible;
    visible = entry.isIntersecting;
    if (visible && wasHidden && !reduce) requestAnimationFrame(frame);
  }).observe(svg);
  function frame(now) {
    const t = reduce ? 11 : ((now - start) / 1000) % STORY_LENGTH;
    let index = 0;
    STORY.forEach(([at], i) => { if (t >= at) index = i; });
    const phase = STORY[index][1];
    if (index !== current) { current = index; onPhase && onPhase(phase); }
    // Walker crosses from right (1260) to left (-60) between 2.4 s and 13.4 s, slowing under the lamp.
    const p = Math.max(0, Math.min(1, (t - 2.4) / 13.6));
    const eased = p + 0.14 * Math.sin(2 * Math.PI * p) / (2 * Math.PI); // slower under the lamp
    const x = 1260 - eased * 1320;
    walker.setAttribute("transform", `translate(${x.toFixed(1)} 402)`);
    walker.style.opacity = t > 2.4 && t < 16 ? 1 : 0;
    const swing = reduce ? 0 : Math.sin(t * 9) * 9;
    legA.setAttribute("x2", (-12 + swing).toFixed(1));
    legB.setAttribute("x2", (12 - swing).toFixed(1));
    detP.style.opacity = t > 3.2 && t < 15.8 ? 1 : 0;
    const armed = t > 9.5 && t < 13.6;
    blade.setAttribute("opacity", armed ? 1 : 0);
    detK.style.opacity = t > 10 && t < 13.6 ? (reduce ? 1 : 0.75 + 0.25 * Math.sin(t * 14)) : 0;
    lamp += ((phase.light / 100) - lamp) * 0.06;
    if (reduce) lamp = phase.light / 100;
    setLamp(svg, lamp);
    if (!reduce && visible) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}
