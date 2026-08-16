import * as THREE from "three";

const LOOP_MS = 9000;
const NONREPRO = "#58BFE0";
const INK = "#14181B";
const GRAPHITE = "#8296A0";
const TEX_W = 640;
const TEX_H = 480;

const ACCEPTED = "The lamp had been dark for nine days when Maren finally climbed the stair.";
const DRAFT = "She counted the steps the way her father had taught her, out of habit more than fear.";

// Phase boundaries as fractions of the 9s loop — mirrors the actual product
// beat (draft arrives in blue, sits for review, then ink-settles) rather
// than a generic typing demo, so a user who later sits in the real galley
// recognizes the moment.
const IDLE_END = 1.5 / 9;
const TYPE_END = 4.5 / 9;
const HOLD_END = 6.0 / 9;
const SWEEP_END = 6.62 / 9;

function wrapLines(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const words = text.split(" ");
  const lines: string[] = [];
  let line = "";
  for (const word of words) {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line);
      line = word;
    } else {
      line = test;
    }
  }
  if (line) lines.push(line);
  return lines;
}

function drawParagraph(
  ctx: CanvasRenderingContext2D,
  lines: string[],
  x: number,
  y: number,
  lineHeight: number,
  colorFor: (charIndex: number) => string | null,
) {
  let charIndex = 0;
  let cy = y;
  for (const line of lines) {
    let cx = x;
    for (const ch of line) {
      const color = colorFor(charIndex);
      if (color) {
        ctx.fillStyle = color;
        ctx.fillText(ch, cx, cy);
      }
      cx += ctx.measureText(ch).width;
      charIndex++;
    }
    charIndex++;
    cy += lineHeight;
  }
  return cy;
}

// Which phase of the 9s loop we're in — drives both what the canvas texture
// draws and whether it needs to be redrawn at all this frame (§7.2/7.3 of
// the animation-flow doc): "idle"/"hold" phases are static for over a
// second at a time, so re-uploading an unchanged 640x480 texture every RAF
// tick would be pure waste.
type Phase = "idle" | "typing" | "hold-blue" | "settling" | "hold-ink";

function phaseFor(loopFrac: number): Phase {
  if (loopFrac < IDLE_END) return "idle";
  if (loopFrac < TYPE_END) return "typing";
  if (loopFrac < HOLD_END) return "hold-blue";
  if (loopFrac < SWEEP_END) return "settling";
  return "hold-ink";
}

function drawTexture(ctx: CanvasRenderingContext2D, loopFrac: number) {
  ctx.fillStyle = "#F6F2E9";
  ctx.fillRect(0, 0, TEX_W, TEX_H);

  ctx.font = "600 15px 'Spline Sans Mono', ui-monospace, monospace";
  ctx.textBaseline = "top";
  ctx.fillStyle = GRAPHITE;
  ctx.fillText("03", 48, 44);

  ctx.font = "400 22px Georgia, serif";
  const maxWidth = TEX_W - 96;
  const acceptedLines = wrapLines(ctx, ACCEPTED, maxWidth);
  const draftLines = wrapLines(ctx, DRAFT, maxWidth);

  const draftY = drawParagraph(ctx, acceptedLines, 48, 96, 32, () => INK) + 20;

  const draftChars = draftLines.join(" ").length;
  const revealFrac = loopFrac < IDLE_END ? 0 : Math.min(1, (loopFrac - IDLE_END) / (TYPE_END - IDLE_END));
  const sweepFrac = loopFrac < HOLD_END ? 0 : Math.min(1, (loopFrac - HOLD_END) / (SWEEP_END - HOLD_END));
  const revealCount = Math.floor(draftChars * revealFrac);
  const inkCount = Math.floor(draftChars * sweepFrac);

  drawParagraph(ctx, draftLines, 48, draftY, 32, (i) => (i < revealCount ? (i < inkCount ? INK : NONREPRO) : null));
}

// A soft round sprite for the dust-mote particles, generated once — same
// "tiny procedural canvas, drawn once, never re-drawn" approach as the
// table-glow texture below.
function makeDotTexture(): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const ctx = c.getContext("2d")!;
  const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, "rgba(255,255,255,0.9)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 64, 64);
  const tex = new THREE.CanvasTexture(c);
  tex.needsUpdate = true;
  return tex;
}

// A plain radial-gradient backlight card behind the sheet — stands in for
// the light table without needing real geometry detail.
function makeGlowTexture(): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const ctx = c.getContext("2d")!;
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, "rgba(120, 200, 224, 0.55)");
  g.addColorStop(1, "rgba(120, 200, 224, 0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(c);
  tex.needsUpdate = true;
  return tex;
}

const VERTEX_SHADER = /* glsl */ `
  uniform float uTime;
  varying vec2 vUv;
  varying vec3 vNormal;

  void main() {
    vUv = uv;
    vec3 pos = position;

    // Two offset, low-frequency sine terms, deliberately different
    // frequency/phase so the surface reads as resting paper with a
    // natural cockle, not a uniform ripple (which reads as water/fabric).
    float waveX = sin(pos.x * 1.6 + uTime * 0.35) * 0.045;
    float waveY = sin(pos.y * 2.3 - uTime * 0.22) * 0.03;
    pos.z += waveX + waveY;

    float dzdx = cos(pos.x * 1.6 + uTime * 0.35) * 1.6 * 0.045;
    float dzdy = cos(pos.y * 2.3 - uTime * 0.22) * 2.3 * -0.03;
    vNormal = normalize(vec3(-dzdx, -dzdy, 1.0));

    gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
  }
`;

const FRAGMENT_SHADER = /* glsl */ `
  uniform sampler2D uMap;
  uniform vec3 uKeyDir;
  uniform vec3 uKeyColor;
  uniform vec3 uFillDir;
  uniform vec3 uFillColor;
  uniform float uAmbient;
  varying vec2 vUv;
  varying vec3 vNormal;

  void main() {
    vec4 tex = texture2D(uMap, vUv);

    float keyTerm = max(dot(vNormal, uKeyDir), 0.0);
    float fillTerm = max(dot(vNormal, uFillDir), 0.0);
    vec3 light = vec3(uAmbient) + uKeyColor * keyTerm * 0.55 + uFillColor * fillTerm * 0.35;

    vec3 color = tex.rgb * light;

    float dist = distance(vUv, vec2(0.5));
    float vignette = smoothstep(0.75, 0.32, dist);
    color *= mix(0.86, 1.0, vignette);

    gl_FragColor = vec4(color, tex.a);
  }
`;

export function createHeroScene(canvas: HTMLCanvasElement) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "low-power" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
  camera.position.set(0, 0.6, 4.2);
  camera.lookAt(0, 0, 0);

  // Sheet — custom-shaded so the vertex warp can displace geometry directly,
  // and so lighting stays a self-contained two-directional + ambient term
  // rather than pulling in MeshStandardMaterial's full PBR/env-map path.
  const texCanvas = document.createElement("canvas");
  texCanvas.width = TEX_W;
  texCanvas.height = TEX_H;
  const texCtx = texCanvas.getContext("2d")!;
  const texture = new THREE.CanvasTexture(texCanvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.generateMipmaps = false;
  texture.minFilter = THREE.LinearFilter;

  const geometry = new THREE.PlaneGeometry(4.2, (TEX_H / TEX_W) * 4.2, 48, 64);
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uMap: { value: texture },
      uKeyDir: { value: new THREE.Vector3(-0.4, 0.6, 0.5).normalize() },
      uKeyColor: { value: new THREE.Color(0xfff3e0) },
      uFillDir: { value: new THREE.Vector3(0, -1, 0.3).normalize() },
      uFillColor: { value: new THREE.Color(0x9fd8ee) },
      uAmbient: { value: 0.32 },
    },
    vertexShader: VERTEX_SHADER,
    fragmentShader: FRAGMENT_SHADER,
  });
  const plane = new THREE.Mesh(geometry, material);
  scene.add(plane);

  // Table glow — unlit, additive, sits behind the sheet. depthWrite:false
  // means it never needs to be depth-sorted against the sheet; additive
  // blending is what makes it read as light rather than a second card.
  const glow = new THREE.Mesh(
    new THREE.PlaneGeometry(6.4, 5.2),
    new THREE.MeshBasicMaterial({
      map: makeGlowTexture(),
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  glow.position.set(0, -0.15, -0.6);
  scene.add(glow);

  // Dust motes — added per explicit request, on top of the design doc's
  // own "no particles" restraint. Kept genuinely restrained: ~40 points,
  // barely visible, additive, no interaction — texture on a light table
  // catching floating dust, not a VFX shower.
  const PARTICLE_COUNT = 40;
  const particleGeometry = new THREE.BufferGeometry();
  const basePositions = new Float32Array(PARTICLE_COUNT * 3);
  const seeds = new Float32Array(PARTICLE_COUNT);
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    basePositions[i * 3] = (Math.random() - 0.5) * 4.6;
    basePositions[i * 3 + 1] = (Math.random() - 0.5) * 3.2;
    basePositions[i * 3 + 2] = Math.random() * 1.2 - 0.2;
    seeds[i] = Math.random() * Math.PI * 2;
  }
  particleGeometry.setAttribute("position", new THREE.BufferAttribute(basePositions.slice(), 3));
  const particles = new THREE.Points(
    particleGeometry,
    new THREE.PointsMaterial({
      map: makeDotTexture(),
      size: 0.03,
      transparent: true,
      opacity: 0.28,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
    }),
  );
  scene.add(particles);

  const key = new THREE.DirectionalLight(0xfff3e0, 0.9);
  key.position.set(-2.2, 2.6, 2.0);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0x9fd8ee, 0.5);
  fill.position.set(0, -1.5, 1.2);
  scene.add(fill);
  scene.add(new THREE.AmbientLight(0xffffff, 0.25));

  let pointerX = 0;
  let pointerY = 0;
  let lastPhase: Phase | null = null;

  function setPointer(nx: number, ny: number) {
    pointerX = nx;
    pointerY = ny;
  }

  function resize(width: number, height: number) {
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }

  function frame(elapsedMs: number) {
    const t = elapsedMs / 1000;
    material.uniforms.uTime.value = t;

    const loopFrac = (elapsedMs % LOOP_MS) / LOOP_MS;
    const phase = phaseFor(loopFrac);
    // Only redraw + reupload the texture on frames where the content can
    // actually have changed — "typing"/"settling" animate every tick,
    // "idle"/"hold-*" are static for well over a second at a time.
    if (phase === "typing" || phase === "settling" || phase !== lastPhase) {
      drawTexture(texCtx, loopFrac);
      texture.needsUpdate = true;
      lastPhase = phase;
    }

    const pos = particleGeometry.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const seed = seeds[i];
      pos.setX(i, basePositions[i * 3] + Math.sin(t * 0.15 + seed) * 0.12);
      pos.setY(i, basePositions[i * 3 + 1] + ((t * 0.06 + seed) % 3.2) - 1.6);
    }
    pos.needsUpdate = true;

    // Camera carries the fixed 14° tilt (set once, above); the plane only
    // carries the pointer-driven ±4° — mixing the two into one rotation
    // would compound them into a much steeper apparent tilt.
    const targetRotZ = pointerX * THREE.MathUtils.degToRad(4);
    const targetRotX = THREE.MathUtils.degToRad(-14) + pointerY * THREE.MathUtils.degToRad(4);
    plane.rotation.z += (targetRotZ - plane.rotation.z) * 0.06;
    plane.rotation.x += (targetRotX - plane.rotation.x) * 0.06;

    renderer.render(scene, camera);
  }

  function dispose() {
    geometry.dispose();
    material.dispose();
    texture.dispose();
    glow.geometry.dispose();
    (glow.material as THREE.MeshBasicMaterial).map?.dispose();
    (glow.material as THREE.MeshBasicMaterial).dispose();
    particleGeometry.dispose();
    (particles.material as THREE.PointsMaterial).map?.dispose();
    (particles.material as THREE.PointsMaterial).dispose();
    renderer.dispose();
  }

  return { setPointer, resize, frame, dispose };
}
