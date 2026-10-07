/* Sentinel Street landing page: three.js night street hero + scroll interactions.
   Falls back to the 2D SVG scene (scene.js) when WebGL or the three.js CDN is unavailable. */

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
// ?t=8.6 freezes the hero story at that second (for screenshots and demos).
const frozenAt = new URLSearchParams(location.search).has("t") ? +new URLSearchParams(location.search).get("t") : null;
if (frozenAt != null) document.documentElement.classList.add("frozen");
const closeUp = new URLSearchParams(location.search).has("close"); // ?close frames the camera on the character (for checking the acting)
const hero = document.getElementById("hero");
const hudEl = document.getElementById("hero-hud");

/* ---------------------------------------------------------------- page UI */
const nav = document.getElementById("lnav");
const onScroll = () => nav.classList.toggle("solid", window.scrollY > 40);
window.addEventListener("scroll", onScroll, { passive: true });
onScroll();

function countUp(el) {
  const to = +el.dataset.to, suffix = el.dataset.suffix || "";
  if (reduceMotion) { el.textContent = `${to}${suffix}`; return; }
  const t0 = performance.now();
  const tick = (now) => {
    const k = Math.min(1, (now - t0) / 1200);
    el.textContent = `${Math.round(to * (1 - Math.pow(1 - k, 3)))}${suffix}`;
    if (k < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
const revealer = new IntersectionObserver((entries) => {
  for (const entry of entries) {
    if (!entry.isIntersecting) continue;
    entry.target.classList.add("in");
    entry.target.querySelectorAll(".count").forEach(countUp);
    revealer.unobserve(entry.target);
  }
}, { threshold: 0.18 });
document.querySelectorAll(".reveal, .steps").forEach((el) => revealer.observe(el));

/* ------------------------------------------------------------ hero HUD */
function setPhase(phase) {
  hudEl.dataset.level = phase.level;
  document.getElementById("hud-level").textContent = phase.level;
  document.getElementById("hud-light").textContent = `${phase.light}%`;
  const buzzer = document.getElementById("hud-buzzer");
  buzzer.textContent = phase.buzzer ? "ON" : "OFF";
  buzzer.style.color = phase.buzzer ? "var(--high)" : "";
  const log = document.getElementById("hud-log");
  log.textContent = phase.text;
  log.classList.remove("flash"); void log.offsetWidth; log.classList.add("flash");
  hero.classList.toggle("alarm", phase.level === "HIGH");
}

function phaseAt(t) {
  let index = 0;
  STORY.forEach(([at], i) => { if (t >= at) index = i; });
  return { index, phase: STORY[index][1] };
}

function fallback2D() {
  document.getElementById("hero3d").hidden = true;
  const box = document.getElementById("hero2d");
  box.hidden = false;
  box.innerHTML = streetScene("hero2dsc");
  playStory(box.querySelector("svg"), setPhase);
}

/* ------------------------------------------------------------ 3D scene */
// a slow or blocked CDN must not leave a black hero: give up after 5 s and use the 2D scene
const within = (promise, ms) => Promise.race([promise, new Promise((resolve) => setTimeout(() => resolve(null), ms))]);
const THREE = await within(import("three").catch(() => null), 5000);
const { GLTFLoader } = THREE ? (await within(import("three/addons/loaders/GLTFLoader.js").catch(() => null), 5000)) || {} : {};
if (!THREE || !init3D(THREE)) fallback2D();

function init3D(THREE) {
  const canvas = document.getElementById("hero3d");
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
  } catch {
    return false;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.45;

  const scene = new THREE.Scene();
  const night = new THREE.Color(0x05070b);
  scene.background = night;
  scene.fog = new THREE.FogExp2(night, 0.042);
  const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 220);

  // seeded random so the city is the same every visit
  let seed = 11;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);

  scene.add(new THREE.HemisphereLight(0x6a80ad, 0x0c0c10, 0.9));
  const moon = new THREE.DirectionalLight(0x8ea4cc, 0.35);
  moon.position.set(-12, 22, 6);
  scene.add(moon);

  /* street */
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(260, 260),
    new THREE.MeshStandardMaterial({ color: 0x101114, roughness: 0.42, metalness: 0.25 })); // damp asphalt catches the lamp
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);
  const walk = new THREE.Mesh(new THREE.BoxGeometry(260, 0.18, 4.4),
    new THREE.MeshStandardMaterial({ color: 0x1a1b1e, roughness: 0.9 }));
  walk.position.set(0, 0.09, -4.4);
  walk.receiveShadow = true;
  scene.add(walk);
  const curb = new THREE.Mesh(new THREE.BoxGeometry(260, 0.22, 0.22), new THREE.MeshStandardMaterial({ color: 0x2b2c30, roughness: 0.8 }));
  curb.position.set(0, 0.11, -2.2);
  scene.add(curb);
  const dashMat = new THREE.MeshStandardMaterial({ color: 0x5a5a55, roughness: 0.7 });
  for (let x = -80; x <= 80; x += 4.5) {
    const dash = new THREE.Mesh(new THREE.BoxGeometry(2.2, 0.012, 0.13), dashMat);
    dash.position.set(x, 0.006, 3.2);
    dash.receiveShadow = true;
    scene.add(dash);
  }

  /* buildings with lit windows */
  function facade() {
    const c = document.createElement("canvas");
    c.width = 128; c.height = 256;
    const g = c.getContext("2d");
    g.fillStyle = "#000"; g.fillRect(0, 0, 128, 256);
    for (let row = 0; row < 16; row++) {
      for (let col = 0; col < 6; col++) {
        if (rnd() < 0.2) {
          const warm = rnd() < 0.75;
          g.fillStyle = warm ? `rgba(255, ${170 + Math.floor(rnd() * 50)}, 90, ${0.55 + rnd() * 0.45})` : `rgba(170, 200, 255, ${0.35 + rnd() * 0.3})`;
          g.fillRect(8 + col * 20, 8 + row * 15.5, 11, 9);
        }
      }
    }
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    return tex;
  }
  const textures = Array.from({ length: 5 }, facade);
  function row(z0, depth, minH, maxH, dim) {
    let x = -90;
    while (x < 90) {
      const w = 4 + rnd() * 6, h = minH + rnd() * (maxH - minH), d = 4 + rnd() * 3;
      const tex = textures[Math.floor(rnd() * textures.length)].clone();
      tex.needsUpdate = true;
      tex.repeat.set(w / 2.4, h / 4.8);
      tex.offset.set(rnd(), rnd());
      const mat = new THREE.MeshStandardMaterial({ color: 0x0b0d11, roughness: 0.92, emissive: 0xffffff, emissiveMap: tex, emissiveIntensity: dim });
      const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
      b.position.set(x + w / 2, h / 2, z0 - rnd() * depth - d / 2);
      scene.add(b);
      x += w + 0.4 + rnd() * 1.2;
    }
  }
  row(-8.5, 3, 7, 20, 0.8);
  row(-24, 6, 16, 42, 0.5);

  /* stars */
  const starGeo = new THREE.BufferGeometry();
  const starPos = new Float32Array(600 * 3);
  for (let i = 0; i < 600; i++) {
    const a = rnd() * Math.PI * 2, r = 120 + rnd() * 40;
    starPos.set([Math.cos(a) * r, 30 + rnd() * 70, -60 - rnd() * 60], i * 3);
  }
  starGeo.setAttribute("position", new THREE.BufferAttribute(starPos, 3));
  scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0xffffff, size: 0.35, transparent: true, opacity: 0.55, fog: false })));

  /* street lamps */
  const metal = new THREE.MeshStandardMaterial({ color: 0x2d3036, roughness: 0.45, metalness: 0.7 });
  const headMat = new THREE.MeshStandardMaterial({ color: 0x3b3e45, roughness: 0.4, metalness: 0.6 });
  function lampPost(x, z) {
    const g = new THREE.Group();
    g.position.set(x, 0, z);
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.1, 5.6, 14), metal);
    pole.position.y = 2.8;
    pole.castShadow = true;
    g.add(pole);
    const arm = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([
      new THREE.Vector3(0, 5.45, 0), new THREE.Vector3(0, 5.9, 0.45), new THREE.Vector3(0, 5.95, 1.15), new THREE.Vector3(0, 5.85, 1.5),
    ]), 24, 0.045, 8), metal);
    arm.castShadow = true;
    g.add(arm);
    const head = new THREE.Mesh(new THREE.BoxGeometry(0.36, 0.11, 0.78), headMat);
    head.position.set(0, 5.82, 1.5);
    head.castShadow = true;
    g.add(head);
    const bulbMat = new THREE.MeshBasicMaterial({ color: 0xffe2a8, toneMapped: false });
    const bulb = new THREE.Mesh(new THREE.PlaneGeometry(0.26, 0.62), bulbMat);
    bulb.rotation.x = Math.PI / 2;
    bulb.position.set(0, 5.76, 1.5);
    g.add(bulb);
    scene.add(g);
    return { group: g, bulbMat, bulbWorld: new THREE.Vector3(x, 5.74, z + 1.5) };
  }
  const main = lampPost(0, -2.7);
  for (const x of [-18, 18, -36, 36]) {
    const side = lampPost(x, -2.7);
    side.bulbMat.color.setRGB(1.6, 1.2, 0.7);
    const s = new THREE.SpotLight(0xffc27a, 55, 16, 0.7, 0.6, 1.7);
    s.position.copy(side.bulbWorld);
    s.target.position.set(x, 0, -1.2);
    scene.add(s, s.target);
  }

  const spot = new THREE.SpotLight(0xffc98a, 0, 26, 0.66, 0.5, 1.4);
  spot.position.copy(main.bulbWorld);
  spot.target.position.set(0, 0, -1.2);
  spot.castShadow = true;
  spot.shadow.mapSize.set(1024, 1024);
  spot.shadow.bias = -0.0004;
  spot.shadow.camera.near = 0.5;
  spot.shadow.camera.far = 14;
  scene.add(spot, spot.target);

  /* volumetric light cone: brighter at the lamp, soft at the edges */
  const coneH = 5.7;
  const coneMat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    uniforms: { uColor: { value: new THREE.Color(0xffb85c) }, uI: { value: 0 }, uH: { value: coneH } },
    vertexShader: `varying float vY; varying vec3 vN; varying vec3 vV;
      void main() { vY = position.y; vec4 mv = modelViewMatrix * vec4(position, 1.0);
        vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform vec3 uColor; uniform float uI; uniform float uH; varying float vY; varying vec3 vN; varying vec3 vV;
      void main() { float t = clamp(vY / uH + 0.5, 0.0, 1.0); float edge = pow(abs(dot(vN, vV)), 1.6);
        float a = (0.04 + pow(t, 2.2) * 0.32) * edge * uI; gl_FragColor = vec4(uColor * a, a); }`,
  });
  const cone = new THREE.Mesh(new THREE.ConeGeometry(3.3, coneH, 64, 1, true), coneMat);
  cone.position.set(0, main.bulbWorld.y - coneH / 2, main.bulbWorld.z);
  scene.add(cone);

  /* dust drifting in the beam */
  const dustCount = 260;
  const dustGeo = new THREE.BufferGeometry();
  const dust = new Float32Array(dustCount * 3);
  const dustSeed = [];
  for (let i = 0; i < dustCount; i++) {
    const y = rnd() * 5.2, r = (1 - y / 5.6) * 3 * Math.sqrt(rnd()), a = rnd() * Math.PI * 2;
    dustSeed.push([Math.cos(a) * r, y, Math.sin(a) * r, rnd() * 6.28]);
  }
  dustGeo.setAttribute("position", new THREE.BufferAttribute(dust, 3));
  const dustMat = new THREE.PointsMaterial({ color: 0xffd9a0, size: 0.035, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending });
  scene.add(new THREE.Points(dustGeo, dustMat));

  /* alarm: red pulse light + beacon on the pole */
  const alarm = new THREE.PointLight(0xff2a2a, 0, 14, 1.8);
  alarm.position.set(0, 5.1, -2.2);
  scene.add(alarm);
  const beaconMat = new THREE.MeshBasicMaterial({ color: 0x330808, toneMapped: false });
  const beacon = new THREE.Mesh(new THREE.SphereGeometry(0.07, 16, 12), beaconMat);
  beacon.position.set(0.1, 5.25, -2.7);
  scene.add(beacon);

  /* the person */
  const skin = new THREE.MeshStandardMaterial({ color: 0x4a4e57, roughness: 0.6 });
  const person = new THREE.Group();
  const add = (parent, mesh, x, y, z) => { mesh.position.set(x, y, z); mesh.castShadow = true; parent.add(mesh); return mesh; };
  add(person, new THREE.Mesh(new THREE.CapsuleGeometry(0.2, 0.52, 6, 14), skin), 0, 1.36, 0);
  add(person, new THREE.Mesh(new THREE.SphereGeometry(0.135, 18, 14), skin), 0, 1.86, 0);
  const limb = (x, y, r, len) => {
    const pivot = new THREE.Group();
    pivot.position.set(x, y, 0);
    add(pivot, new THREE.Mesh(new THREE.CapsuleGeometry(r, len, 5, 10), skin), 0, -len / 2 - r, 0);
    person.add(pivot);
    return pivot;
  };
  const legL = limb(0, 0.95, 0.075, 0.72), legR = limb(0, 0.95, 0.075, 0.72);
  legL.position.z = 0.1; legR.position.z = -0.1;
  const armL = limb(0, 1.6, 0.06, 0.5), armR = limb(0, 1.6, 0.06, 0.5);
  armL.position.z = 0.27; armR.position.z = -0.27;
  const knife = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.3, 0.05),
    new THREE.MeshStandardMaterial({ color: 0xdfe3e8, roughness: 0.2, metalness: 1 }));
  knife.position.set(-0.05, -0.78, 0);
  knife.rotation.z = 0.5;
  knife.visible = false;
  armR.add(knife);
  const actor = new THREE.Group();
  actor.position.set(30, 0, -1.0);
  actor.add(person);
  scene.add(actor);

  /* the intruder: rigged human with motion-captured walk / idle / run, dark clothes, knife in hand */
  let rig = null;
  const blade = new THREE.Group();
  blade.add(new THREE.Mesh(new THREE.BoxGeometry(0.022, 0.2, 0.045), new THREE.MeshStandardMaterial({ color: 0xf2f4f7, roughness: 0.22, metalness: 0.35 })));
  const grip = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.11, 0.035), new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.6 }));
  grip.position.y = -0.15;
  blade.add(grip);
  blade.visible = false;
  /* Michelle (human) is what you see. The motion-captured Walk / Idle / Run come from the
     Mixamo "Vanguard" rig and are retargeted onto her skeleton; that rig itself is never shown. */
  if (GLTFLoader) {
    const loader = new GLTFLoader();
    const load = (url) => new Promise((resolve, reject) => loader.load(url, resolve, undefined, reject));
    Promise.all([load("/static/models/human.glb"), load("/static/models/mocap-source.glb")]).then(([human, motion]) => {
      const model = human.scene;
      // calibrate both rigs from their own T-pose clips, then build the retargeter from those poses
      for (const [root, clips] of [[motion.scene, motion.animations], [model, human.animations]]) {
        const tpose = clips.find((c) => c.name === "TPose");
        if (!tpose) continue;
        const m = new THREE.AnimationMixer(root);
        m.clipAction(tpose).play();
        m.update(0); // left active on purpose: stopping it would restore the original pose before we capture it
      }
      const retarget = makeRetargeter(THREE, motion.scene, model);
      const dark = new THREE.MeshStandardMaterial({ color: 0x15161a, roughness: 0.9 });
      model.traverse((o) => {
        if (!o.isMesh) return;
        o.castShadow = true;
        const m = o.material.clone();
        if (m.map) m.map = darkenClothes(THREE, m.map);
        m.color.setRGB(0.75, 0.72, 0.7);
        m.roughness = 0.85;
        o.material = m;
      });
      const bone = (name) => model.getObjectByName(name) || model.getObjectByName(name.replace(":", ""));
      model.updateMatrixWorld(true);
      const scaleOf = (o) => o.getWorldScale(new THREE.Vector3()).x;
      // knife in the hand nearest the camera (the figure walks right-to-left, so that's the left hand)
      const hand = bone("mixamorig:LeftHand");
      if (hand) {
        const k = 1 / scaleOf(hand);
        blade.scale.setScalar(k);
        blade.position.set(-0.02 * k, 0.08 * k, 0.03 * k);
        blade.rotation.set(0, 0, -Math.PI / 2);
        hand.add(blade);
      }
      const head = bone("mixamorig:Head");
      if (head) {
        const beanie = new THREE.Mesh(new THREE.SphereGeometry(0.115, 20, 12, 0, Math.PI * 2, 0, Math.PI / 1.85), dark);
        beanie.scale.setScalar(1 / scaleOf(head));
        beanie.position.y = 0.1 / scaleOf(head);
        beanie.castShadow = true;
        head.add(beanie);
      }
      // the (hidden) source rig plays the clips; retarget() copies its pose onto the human every frame
      const mixer = new THREE.AnimationMixer(motion.scene);
      const actions = Object.fromEntries(motion.animations.map((clip) => [clip.name, mixer.clipAction(clip)]));
      // Face the direction of travel (-x): measure where the toes point instead of assuming the model's axis.
      const foot = bone("mixamorig:LeftFoot"), toe = bone("mixamorig:LeftToeBase");
      let yaw = 0;
      if (foot && toe) {
        const a = foot.getWorldPosition(new THREE.Vector3()), b = toe.getWorldPosition(new THREE.Vector3());
        yaw = Math.atan2(b.x - a.x, b.z - a.z);
      }
      model.rotation.y = -Math.PI / 2 - yaw;
      person.visible = false;
      actor.remove(person);
      actor.add(model);
      rig = { mixer, actions, current: null, retarget, model, baseYaw: model.rotation.y, act: makeActing(THREE, model, bone) };
      redrawIfStill(); // reduced motion draws a single frame: draw it again now the character exists
    }).catch((error) => console.warn("Human model unavailable, using simple figure:", error));
  }
  function play(name) {
    if (!rig || rig.current === name || !rig.actions[name]) return;
    const next = rig.actions[name].reset().play();
    if (rig.current) rig.actions[rig.current].crossFadeTo(next, 0.35, false);
    rig.current = name;
  }

  /* camera rig */
  const pointer = { x: 0, y: 0 };
  window.addEventListener("pointermove", (e) => {
    pointer.x = e.clientX / window.innerWidth - 0.5;
    pointer.y = e.clientY / window.innerHeight - 0.5;
  }, { passive: true });
  const lookAt = new THREE.Vector3();
  const view = { w: canvas.clientWidth, h: canvas.clientHeight };
  // with reduced motion (or a frozen ?t= still) nothing animates, so redraw explicitly after changes
  function redrawIfStill() {
    if ((reduceMotion || frozenAt != null) && typeof frame === "function") frame(performance.now());
  }

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    view.w = w; view.h = h; // cached so project() doesn't force a layout every frame
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // keep the lamp right of centre on wide screens, centred on phones
    camera.userData.shift = w / h > 1.2 ? -2.3 : 0;
    camera.fov = w / h > 1.2 ? 36 : 50;
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", () => { resize(); redrawIfStill(); });
  resize();

  /* projected detection boxes */
  const detPerson = document.getElementById("det-person");
  const detKnife = document.getElementById("det-knife");
  const box3 = new THREE.Box3(), v = new THREE.Vector3();
  function project(object, el, pad, visible) {
    if (!visible) { el.hidden = true; return; }
    box3.setFromObject(object);
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (let i = 0; i < 8; i++) {
      v.set(i & 1 ? box3.max.x : box3.min.x, i & 2 ? box3.max.y : box3.min.y, i & 4 ? box3.max.z : box3.min.z).project(camera);
      const sx = (v.x * 0.5 + 0.5) * view.w, sy = (-v.y * 0.5 + 0.5) * view.h;
      minX = Math.min(minX, sx); maxX = Math.max(maxX, sx); minY = Math.min(minY, sy); maxY = Math.max(maxY, sy);
    }
    el.hidden = false;
    Object.assign(el.style, { left: `${minX - pad}px`, top: `${minY - pad}px`, width: `${maxX - minX + pad * 2}px`, height: `${maxY - minY + pad * 2}px` });
  }

  /* animation */
  let lamp = frozenAt != null ? phaseAt(frozenAt).phase.light / 100 : 0.2, current = -1, running = true, last = performance.now(), start = last;
  const hold = 11; // reduced motion: freeze on the HIGH moment with the person under the lamp
  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    const t = frozenAt ?? (reduceMotion ? hold : ((now - start) / 1000) % STORY_LENGTH);
    const { index, phase } = phaseAt(t);
    if (index !== current) { current = index; setPhase(phase); }

    // walk in from the right, stop under the lamp for the incident, then walk off left
    const ease = (k) => k * k * (3 - 2 * k);
    // Choreography: walk in (2.4-6.4) · turn and look back (6.6-8.8) · hand to pocket (8.8-9.5)
    // · pull the knife and raise it (9.5-10.2) · hold (HIGH) · run off (13.4-15.8)
    const span = (a, b) => ease(Math.max(0, Math.min(1, (t - a) / (b - a))));
    const inK = Math.max(0, Math.min(1, (t - 2.4) / 4.2)), outK = Math.max(0, Math.min(1, (t - 13.4) / 2.4));
    actor.position.x = t < 13.4 ? 9 - 8.4 * (1 - Math.pow(1 - inK, 1.6)) : 0.6 - 15 * ease(outK);
    person.rotation.y = Math.PI;
    const walking = t > 2.4 && t < 16;
    const moving = (t > 2.4 && t < 6.4) || t > 13.4;
    actor.visible = walking;
    if (rig) {
      play(t > 13.4 ? "Run" : moving ? "Walk" : "Idle");
      rig.actions.Walk && (rig.actions.Walk.timeScale = 1.35);
      rig.mixer.update(frozenAt != null ? 0 : dt);
      rig.retarget();
      // turn round towards the camera side to look back the way she came, then face forward again
      const turn = 2.85 * (span(6.6, 7.3) - span(8.2, 8.8));
      rig.model.rotation.y = rig.baseYaw + turn;
      rig.model.updateMatrixWorld(true);
      const lookWeight = span(6.9, 7.2) * (1 - span(8.0, 8.4));
      rig.act.look(lookWeight * 0.55 * Math.sin(((t - 7.0) / 1.3) * Math.PI * 2)); // scanning the street
      // reach into the hip pocket, then draw the knife up into a threatening hold
      const reach = span(8.8, 9.3) * (1 - span(13.0, 13.5));
      const draw = span(9.5, 10.2);
      rig.act.reach(reach, draw, reduceMotion ? 0 : Math.sin(t * 2.2) * 0.03);
    }
    const pace = reduceMotion || !moving ? 0 : Math.sin(t * 7.5);
    legL.rotation.z = pace * 0.45; legR.rotation.z = -pace * 0.45;
    const armed = t > 9.45 && t < 13.6;
    knife.visible = armed;
    blade.visible = armed;
    armL.rotation.z = -pace * 0.35;
    armR.rotation.z = armed ? THREE.MathUtils.lerp(armR.rotation.z, 1.05, 0.12) : pace * 0.35;

    // lamp
    lamp += (phase.light / 100 - lamp) * (1 - Math.exp(-dt * 3.2));
    spot.intensity = 900 * Math.pow(lamp, 0.7);
    coneMat.uniforms.uI.value = 0.5 + lamp * 1.9;
    dustMat.opacity = 0.15 + lamp * 0.65;
    main.bulbMat.color.setRGB(0.6 + 2.2 * lamp, 0.45 + 1.7 * lamp, 0.25 + 1.0 * lamp);
    const pos = dustGeo.attributes.position;
    for (let i = 0; i < dustCount; i++) {
      const [dx, dy, dz, ph] = dustSeed[i];
      pos.setXYZ(i, dx + Math.sin(now / 2400 + ph) * 0.12, cone.position.y - coneH / 2 + ((dy + now / 9000) % 5.2), main.bulbWorld.z + dz + Math.cos(now / 2800 + ph) * 0.12);
    }
    pos.needsUpdate = true;

    // alarm
    const high = phase.level === "HIGH";
    const pulse = 0.5 + 0.5 * Math.sin(now / 90);
    alarm.intensity = high ? 30 * pulse : 0;
    beaconMat.color.setRGB(high ? 1.5 + 2 * pulse : 0.2, high ? 0.1 : 0.03, high ? 0.1 : 0.03);

    // camera: slow drift + pointer parallax + scroll rise
    const scroll = Math.min(1, window.scrollY / window.innerHeight);
    const drift = reduceMotion ? 0 : Math.sin(now / 9000) * 0.7;
    camera.position.set(7.5 + drift + pointer.x * 1.2, 2.6 + scroll * 2.4 - pointer.y * 0.5, 11.5 - scroll * 2);
    lookAt.set(camera.userData.shift, 2.25 + scroll * 0.6, -1.6);
    if (closeUp) { camera.position.set(actor.position.x - 0.9, 1.35, actor.position.z + 3.2); lookAt.set(actor.position.x, 1.05, actor.position.z); }
    camera.lookAt(lookAt);

    renderer.render(scene, camera);
    canvas.classList.add("ready");
    project(actor, detPerson, 6, walking && t > 3.2 && t < 15.8);
    project(rig ? blade : knife, detKnife, 12, armed && t > 10.0);
    if (frozenAt != null) setTimeout(() => frame(performance.now()), 120); // timer, so frozen frames render even in a hidden tab
    else if (running && !reduceMotion) requestAnimationFrame(frame);
  }
  if (frozenAt != null) setTimeout(() => frame(performance.now()), 0); else requestAnimationFrame(frame);

  // pause rendering when the hero is scrolled away
  new IntersectionObserver(([entry]) => {
    const visible = entry.isIntersecting;
    if (visible && !running && !reduceMotion && frozenAt == null) { running = true; last = performance.now(); requestAnimationFrame(frame); }
    running = visible;
  }).observe(hero);
  return true;
}

/* Live Mixamo -> Mixamo retargeting. Both rigs share bone names but have different rest orientations,
   so for every bone we take the source's rotation relative to its own rest pose (in rig space) and
   apply that same rotation on top of the target's rest pose. Hip translation is scaled by leg length. */
function makeRetargeter(THREE, sourceRoot, targetRoot) {
  const hipsName = "mixamorigHips";
  const find = (root) => {
    const map = {};
    root.traverse((o) => { if (o.isBone) map[o.name] = o; });
    return map;
  };
  const src = find(sourceRoot), tgt = find(targetRoot);
  const chainQuat = (node, root) => {
    const q = new THREE.Quaternion(), chain = [];
    for (let o = node; o && o !== root; o = o.parent) chain.unshift(o);
    chain.forEach((n) => q.multiply(n.quaternion));
    return q;
  };
  const chainMatrix = (node, root) => {
    const m = new THREE.Matrix4(), chain = [];
    for (let o = node; o && o !== root; o = o.parent) chain.unshift(o);
    chain.forEach((n) => { n.updateMatrix(); m.multiply(n.matrix); });
    return m;
  };
  const order = [];
  (function walk(bone) { order.push(bone.name); bone.children.forEach((c) => c.isBone && walk(c)); })(tgt[hipsName]);
  const names = order.filter((n) => src[n]);
  const srcRest = {}, tgtRest = {};
  for (const n of names) { srcRest[n] = chainQuat(src[n], sourceRoot); tgtRest[n] = chainQuat(tgt[n], targetRoot); }
  const srcHipParent = chainQuat(src[hipsName].parent, sourceRoot), tgtHipParent = chainQuat(tgt[hipsName].parent, targetRoot);
  const srcHipParentM = chainMatrix(src[hipsName].parent, sourceRoot), tgtHipParentM = chainMatrix(tgt[hipsName].parent, targetRoot);
  const srcHipRest = src[hipsName].position.clone().applyMatrix4(srcHipParentM);
  const tgtHipRest = tgt[hipsName].position.clone().applyMatrix4(tgtHipParentM);
  const ratio = tgtHipRest.y / srcHipRest.y;
  // The rigs may face different ways in their own space (here -z vs +z): measure each facing from the
  // foot -> toe direction and convert source motion into the target's frame.
  const facing = (bones, root) => {
    const a = new THREE.Vector3().setFromMatrixPosition(chainMatrix(bones.mixamorigLeftFoot, root));
    const b = new THREE.Vector3().setFromMatrixPosition(chainMatrix(bones.mixamorigLeftToeBase, root));
    return Math.atan2(b.x - a.x, b.z - a.z);
  };
  const turn = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), facing(tgt, targetRoot) - facing(src, sourceRoot));
  const turnInv = turn.clone().invert();
  const tgtHipParentInv = tgtHipParentM.clone().invert();
  const srcWorld = {}, tgtWorld = {}, delta = new THREE.Quaternion(), inv = new THREE.Quaternion(), p = new THREE.Vector3();

  return function retarget() {
    for (const n of names) {
      const s = src[n], t = tgt[n];
      const sParent = n === hipsName ? srcHipParent : srcWorld[s.parent.name];
      srcWorld[n] = (srcWorld[n] || new THREE.Quaternion()).copy(sParent).multiply(s.quaternion);
      delta.copy(srcWorld[n]).multiply(inv.copy(srcRest[n]).invert());
      delta.premultiply(turn).multiply(turnInv);
      const want = (tgtWorld[n] || new THREE.Quaternion()).copy(delta).multiply(tgtRest[n]);
      tgtWorld[n] = want;
      const tParent = n === hipsName ? tgtHipParent : tgtWorld[t.parent.name];
      t.quaternion.copy(inv.copy(tParent).invert()).multiply(want);
    }
    // hips: keep the vertical bob / sway, scaled to the target's size
    p.copy(src[hipsName].position).applyMatrix4(srcHipParentM).sub(srcHipRest).applyQuaternion(turn).multiplyScalar(ratio).add(tgtHipRest);
    tgt[hipsName].position.copy(p.applyMatrix4(tgtHipParentInv));
  };
}

/* Recolour bright clothing in the character texture to near-black, keeping skin tones,
   so the figure reads as someone in dark clothes at night. */
function darkenClothes(THREE, texture) {
  const img = texture.image;
  const w = img.width, h = img.height;
  const canvas = document.createElement("canvas");
  canvas.width = w; canvas.height = h;
  const g = canvas.getContext("2d");
  g.drawImage(img, 0, 0);
  const data = g.getImageData(0, 0, w, h);
  const px = data.data;
  for (let i = 0; i < px.length; i += 4) {
    const r = px[i] / 255, gr = px[i + 1] / 255, b = px[i + 2] / 255;
    const max = Math.max(r, gr, b), min = Math.min(r, gr, b), sat = max ? (max - min) / max : 0;
    let hue = 0;
    if (max !== min) {
      hue = max === r ? ((gr - b) / (max - min)) % 6 : max === gr ? (b - r) / (max - min) + 2 : (r - gr) / (max - min) + 4;
      hue = (hue * 60 + 360) % 360;
    }
    const skin = hue >= 5 && hue <= 38 && sat > 0.18 && sat < 0.75 && max > 0.2;
    if (!skin && (sat > 0.22 || max > 0.55)) {
      const v = 0.07 + max * 0.12; // charcoal, with a little of the original shading kept
      px[i] = px[i + 1] = px[i + 2] = Math.round(v * 255);
      px[i + 2] = Math.round((v + 0.012) * 255);
    }
  }
  g.putImageData(data, 0, 0);
  const out = new THREE.CanvasTexture(canvas);
  out.colorSpace = texture.colorSpace;
  out.flipY = texture.flipY;
  out.wrapS = texture.wrapS; out.wrapT = texture.wrapT;
  return out;
}

/* Acting on top of the mocap: a head scan and a two-bone IK left arm that reaches into the hip
   pocket and then raises the knife. Every pose is blended with the underlying animation by weight. */
function makeActing(THREE, model, bone) {
  const arm = bone("mixamorig:LeftArm"), fore = bone("mixamorig:LeftForeArm"), hand = bone("mixamorig:LeftHand");
  const hip = bone("mixamorig:LeftUpLeg"), neck = bone("mixamorig:Neck"), head = bone("mixamorig:Head");
  const up = new THREE.Vector3(0, 1, 0);
  const S = new THREE.Vector3(), E = new THREE.Vector3(), H = new THREE.Vector3(), T = new THREE.Vector3();
  const tmpQ = new THREE.Quaternion(), parentQ = new THREE.Quaternion(), animQ = new THREE.Quaternion();
  const v1 = new THREE.Vector3(), v2 = new THREE.Vector3();

  // body frame from the model's current heading (the mocap faces the model's forward axis)
  function frame() {
    const forward = new THREE.Vector3(-1, 0, 0).applyAxisAngle(up, model.rotation.y - model.userData.baseYaw);
    const left = new THREE.Vector3().crossVectors(up, forward).normalize();
    return { forward, left };
  }
  model.userData.baseYaw = model.rotation.y;

  // rotate a bone in world space so that its direction `from` points along `to`
  function aim(b, from, to) {
    tmpQ.setFromUnitVectors(v1.copy(from).normalize(), v2.copy(to).normalize());
    b.getWorldQuaternion(animQ);
    b.parent.getWorldQuaternion(parentQ);
    b.quaternion.copy(parentQ.invert().multiply(tmpQ.multiply(animQ)));
    b.updateMatrixWorld(true);
  }
  function blendAim(b, from, to, weight) {
    const start = b.quaternion.clone();
    aim(b, from, to);
    b.quaternion.copy(start.slerp(b.quaternion, weight));
    b.updateMatrixWorld(true);
  }

  function look(angle) {
    if (!neck || !head || Math.abs(angle) < 1e-3) return;
    for (const [b, share] of [[neck, 0.4], [head, 0.6]]) {
      b.getWorldQuaternion(animQ);
      b.parent.getWorldQuaternion(parentQ);
      tmpQ.setFromAxisAngle(up, angle * share);
      b.quaternion.copy(parentQ.invert().multiply(tmpQ.multiply(animQ)));
      b.updateMatrixWorld(true);
    }
  }

  function reach(weight, draw, sway) {
    if (!arm || !fore || !hand || !hip || weight <= 0.001) return;
    const { forward, left } = frame();
    arm.getWorldPosition(S); fore.getWorldPosition(E); hand.getWorldPosition(H);
    const a = S.distanceTo(E), b = E.distanceTo(H);
    // pocket: front of the left hip, a little low; threat: hand out in front of the chest
    const pocket = hip.getWorldPosition(new THREE.Vector3()).addScaledVector(forward, 0.06).addScaledVector(left, 0.08).addScaledVector(up, -0.1);
    const threat = S.clone().addScaledVector(forward, 0.34).addScaledVector(left, 0.14).addScaledVector(up, -0.26 + sway);
    T.copy(pocket).lerp(threat, draw).addScaledVector(up, Math.sin(Math.PI * draw) * 0.1);
    const pole = new THREE.Vector3().addScaledVector(forward, -1 + draw * 0.8).addScaledVector(left, 0.6).addScaledVector(up, -draw);

    // two-bone IK: elbow on the circle where both bone lengths fit, bent toward the pole
    const toT = v1.copy(T).sub(S);
    const d = Math.max(Math.abs(a - b) + 1e-3, Math.min(a + b - 1e-3, toT.length()));
    const dir = toT.normalize().clone();
    const x = (a * a - b * b + d * d) / (2 * d), h = Math.sqrt(Math.max(a * a - x * x, 0));
    const bend = pole.sub(dir.clone().multiplyScalar(pole.dot(dir))).normalize();
    const elbow = S.clone().addScaledVector(dir, x).addScaledVector(bend, h);

    blendAim(arm, E.clone().sub(S), elbow.sub(S), weight);
    fore.getWorldPosition(E); hand.getWorldPosition(H);
    blendAim(fore, H.clone().sub(E), T.clone().sub(E), weight);
  }

  return { look, reach };
}
