import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import './Mascot3D.css';

/**
 * Procedural 3D mascot, built from primitives in code rather than loaded from a model
 * file — so there is no asset to license, source or ship.
 *
 * Swap the palette to re-skin: UB_PALETTE is the university's maroon and gold, BLUE is
 * the placeholder standing in for the real mascot.
 */
const BLUE = { fur: 0x2f9fd6, furTip: 0x63c4ef, mouth: 0x141414, tongue: 0x8c2b3f };
const UB_PALETTE = { fur: 0x7a1220, furTip: 0xffc454, mouth: 0x141414, tongue: 0x8c2b3f };

const MASCOT = {
  palette: BLUE, // <- change to UB_PALETTE for maroon and gold
  radius: 1,
  furShells: 14,
  furLength: 0.17,
  eyeRadius: 0.36,
  eyeSpread: 0.42,
  eyeHeight: 0.66,
  eyeForward: 0.6,
  maxJawAngle: 0.62,
};

/** Noise texture used as the alpha mask for each fur shell. */
function makeFurAlpha(size = 256, density = 0.42) {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  const image = ctx.createImageData(size, size);
  for (let i = 0; i < size * size; i += 1) {
    const on = Math.random() < density ? 255 : 0;
    image.data[i * 4] = 255;
    image.data[i * 4 + 1] = 255;
    image.data[i * 4 + 2] = 255;
    image.data[i * 4 + 3] = on;
  }
  ctx.putImageData(image, 0, 0);
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(4, 4);
  return texture;
}

export default function Mascot3D({ jawOpen = 0, speaking = false, thinking = false }) {
  const mountRef = useRef(null);
  const stateRef = useRef({ jawOpen: 0, speaking: false, thinking: false });

  // Let the animation loop read fresh values without rebuilding the scene.
  stateRef.current.jawOpen = jawOpen;
  stateRef.current.speaking = speaking;
  stateRef.current.thinking = thinking;

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
    camera.position.set(0, 0.1, 4.7);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.8));
    const key = new THREE.DirectionalLight(0xffffff, 1.5);
    key.position.set(2.5, 3, 4);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0xffc454, 0.8);
    rim.position.set(-3, 1, -2);
    scene.add(rim);

    const palette = MASCOT.palette;
    const root = new THREE.Group();
    scene.add(root);

    const headGroup = new THREE.Group();
    root.add(headGroup);

    const disposables = [];

    const skinMat = new THREE.MeshStandardMaterial({ color: palette.fur, roughness: 0.95 });
    disposables.push(skinMat);

    // Dark interior, so an open mouth reads as a cavity rather than a hole.
    const mouthGeo = new THREE.SphereGeometry(MASCOT.radius * 0.94, 32, 24);
    const mouthMat = new THREE.MeshStandardMaterial({
      color: palette.mouth,
      roughness: 1,
      side: THREE.BackSide,
    });
    headGroup.add(new THREE.Mesh(mouthGeo, mouthMat));
    disposables.push(mouthGeo, mouthMat);

    const tongueGeo = new THREE.SphereGeometry(MASCOT.radius * 0.44, 24, 16);
    const tongueMat = new THREE.MeshStandardMaterial({ color: palette.tongue, roughness: 0.85 });
    const tongue = new THREE.Mesh(tongueGeo, tongueMat);
    tongue.scale.set(1, 0.38, 0.9);
    headGroup.add(tongue);
    disposables.push(tongueGeo, tongueMat);

    const furAlpha = makeFurAlpha();
    disposables.push(furAlpha);

    // One half of the head, with fur shells grown outward from it.
    const buildShell = (isUpper) => {
      const group = new THREE.Group();
      const phiStart = isUpper ? 0 : Math.PI / 2;
      const phiLength = Math.PI / 2;

      const baseGeo = new THREE.SphereGeometry(
        MASCOT.radius, 48, 32, 0, Math.PI * 2, phiStart, phiLength,
      );
      group.add(new THREE.Mesh(baseGeo, skinMat));
      disposables.push(baseGeo);

      for (let i = 1; i <= MASCOT.furShells; i += 1) {
        const t = i / MASCOT.furShells;
        const geo = new THREE.SphereGeometry(
          MASCOT.radius + MASCOT.furLength * t, 40, 28, 0, Math.PI * 2, phiStart, phiLength,
        );
        const mat = new THREE.MeshStandardMaterial({
          color: new THREE.Color(palette.fur).lerp(new THREE.Color(palette.furTip), t),
          alphaMap: furAlpha,
          transparent: true,
          alphaTest: 0.02 + t * 0.55, // strands thin out toward the tips
          roughness: 1,
          depthWrite: false,
        });
        group.add(new THREE.Mesh(geo, mat));
        disposables.push(geo, mat);
      }
      return group;
    };

    headGroup.add(buildShell(true));

    // The jaw pivots at the mouth line so it swings open rather than sliding down.
    const jawPivot = new THREE.Group();
    jawPivot.add(buildShell(false));
    headGroup.add(jawPivot);

    const eyeWhiteGeo = new THREE.SphereGeometry(MASCOT.eyeRadius, 32, 24);
    const eyeWhiteMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.3 });
    const pupilGeo = new THREE.SphereGeometry(MASCOT.eyeRadius * 0.45, 24, 18);
    const pupilMat = new THREE.MeshStandardMaterial({ color: 0x101010, roughness: 0.2 });
    disposables.push(eyeWhiteGeo, eyeWhiteMat, pupilGeo, pupilMat);

    const eyes = [];
    for (const side of [-1, 1]) {
      const eye = new THREE.Group();
      const white = new THREE.Mesh(eyeWhiteGeo, eyeWhiteMat);
      const pupil = new THREE.Mesh(pupilGeo, pupilMat);
      pupil.position.z = MASCOT.eyeRadius * 0.72;
      eye.add(white);
      eye.add(pupil);
      eye.position.set(side * MASCOT.eyeSpread, MASCOT.eyeHeight, MASCOT.eyeForward);
      headGroup.add(eye);
      eyes.push({ group: eye, white, pupil, side });
    }

    const resize = () => {
      const width = mount.clientWidth;
      const height = mount.clientHeight;
      if (!width || !height) return;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(mount);

    const reduceMotion = window.matchMedia
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false;

    const clock = new THREE.Clock();
    let smoothedJaw = 0;
    let nextBlink = 2 + Math.random() * 3;
    let blinkUntil = -1;
    let frame = 0;

    const tick = () => {
      frame = requestAnimationFrame(tick);
      const delta = clock.getDelta();
      const time = clock.elapsedTime;
      const current = stateRef.current;

      // Ease toward the target so the jaw does not chatter frame to frame.
      smoothedJaw += (current.jawOpen - smoothedJaw) * Math.min(1, delta * 18);
      jawPivot.rotation.x = smoothedJaw * MASCOT.maxJawAngle;
      tongue.position.y = -MASCOT.radius * (0.42 + smoothedJaw * 0.26);
      tongue.position.z = 0.16;

      if (!reduceMotion) {
        root.rotation.y = Math.sin(time * 0.6) * 0.16;
        root.rotation.z = Math.sin(time * 0.9) * 0.03;
        root.position.y = Math.sin(time * 1.5) * 0.035;
        if (current.thinking) root.rotation.z += Math.sin(time * 6) * 0.04;
      }

      if (time > nextBlink && blinkUntil < 0) blinkUntil = time + 0.13;
      const blinking = blinkUntil > 0 && time < blinkUntil;
      if (blinkUntil > 0 && time >= blinkUntil) {
        blinkUntil = -1;
        nextBlink = time + 2 + Math.random() * 3.5;
      }

      for (const eye of eyes) {
        eye.white.scale.y = blinking ? 0.08 : 1;
        eye.pupil.visible = !blinking;
        if (!reduceMotion) {
          eye.pupil.position.x = Math.sin(time * 0.8 + eye.side) * 0.05;
          eye.pupil.position.y = Math.cos(time * 0.6) * 0.04;
        }
      }

      renderer.render(scene, camera);
    };
    tick();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      for (const item of disposables) item.dispose();
      renderer.dispose();
      // Release the WebGL context, or repeated toggling exhausts the browser's supply.
      if (renderer.forceContextLoss) renderer.forceContextLoss();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
    };
  }, []);

  return (
    <div
      ref={mountRef}
      className={`mascot3d ${speaking ? 'is-speaking' : ''} ${thinking ? 'is-thinking' : ''}`}
      role="img"
      aria-label="UB There mascot"
    />
  );
}
