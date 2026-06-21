import * as THREE from "three";
import { OrbitControls } from "https://esm.sh/three@0.164.1/examples/jsm/controls/OrbitControls.js?external=three";
import { STLLoader } from "https://esm.sh/three@0.164.1/examples/jsm/loaders/STLLoader.js?external=three";
import { STLExporter } from "https://esm.sh/three@0.164.1/examples/jsm/exporters/STLExporter.js?external=three";
import {
  Brush,
  Evaluator,
  INTERSECTION,
  SUBTRACTION
} from "https://esm.sh/three-bvh-csg@0.0.16?external=three";

// ---------- CHERRY MX CONSTANTS ----------

const TOP_OUTPUT = "clicker_top.stl";
const BOTTOM_OUTPUT = "clicker_bottom.stl";

const HOUSING_SIZE = 16.0;
const HOUSING_DEPTH = 5.2;
const CENTER_BOSS_SIZE = 7.0;

const CROSS_WIDTH = 4.20;
const CROSS_ARM = 1.45;
const CROSS_DEPTH = 4.2;

const BOTTOM_CAVITY_SIZE = 16.0;
const BOTTOM_CAVITY_DEPTH = 5.2;

const CENTER_HOLE_DIA = 4.00;
const FIXATION_PIN_DIA = 1.80;
const CONTACT_PIN_DIA = 1.60;

const HOLE_DEPTH = BOTTOM_CAVITY_DEPTH + 5.0;

const GRID = 1.27;

const PIN_HOLES = [
  [0.00, 0.00, CENTER_HOLE_DIA],
  [-4 * GRID, 0.00, FIXATION_PIN_DIA],
  [4 * GRID, 0.00, FIXATION_PIN_DIA],
  [-3 * GRID, 2 * GRID, CONTACT_PIN_DIA],
  [2 * GRID, 4 * GRID, CONTACT_PIN_DIA],
];

// ---------- DOM ----------

const fileInput = document.getElementById("fileInput");
const fileStatus = document.getElementById("fileStatus");
const scaleSlider = document.getElementById("scaleSlider");
const scaleValue = document.getElementById("scaleValue");
const sliceSlider = document.getElementById("sliceSlider");
const sliceValue = document.getElementById("sliceValue");
const warnings = document.getElementById("warnings");
const generateButton = document.getElementById("generateButton");
const generateStatus = document.getElementById("generateStatus");
const downloadTop = document.getElementById("downloadTop");
const downloadBottom = document.getElementById("downloadBottom");
const resetCameraButton = document.getElementById("resetCamera");
const stats = document.getElementById("stats");
const viewer = document.getElementById("viewer");

// ---------- THREE SETUP ----------

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xebe5dd);

const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100000);
camera.position.set(60, -80, 55);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
viewer.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

const ambientLight = new THREE.AmbientLight(0xffffff, 0.65);
scene.add(ambientLight);

const keyLight = new THREE.DirectionalLight(0xffffff, 1.0);
keyLight.position.set(60, -80, 100);
scene.add(keyLight);

const grid = new THREE.GridHelper(120, 24, 0xaaa196, 0xcfc6ba);
grid.rotation.x = Math.PI / 2;
scene.add(grid);

let originalGeometry = null;
let previewMesh = null;
let slicePlaneMesh = null;
let mxReference = null;
let finalGroup = null;
let currentBounds = null;

const materialPreview = new THREE.MeshStandardMaterial({
  color: 0xb8b0a8,
  roughness: 0.6,
  metalness: 0.05,
  transparent: true,
  opacity: 0.58,
  side: THREE.DoubleSide
});

const materialPlane = new THREE.MeshStandardMaterial({
  color: 0xe23d3d,
  transparent: true,
  opacity: 0.38,
  side: THREE.DoubleSide
});

const materialTop = new THREE.MeshStandardMaterial({
  color: 0xd85a5a,
  roughness: 0.55,
  side: THREE.DoubleSide
});

const materialBottom = new THREE.MeshStandardMaterial({
  color: 0x3e7bd6,
  roughness: 0.55,
  side: THREE.DoubleSide
});

const materialMX = new THREE.LineBasicMaterial({
  color: 0x1f9d55
});

// ---------- BASIC UTILITIES ----------

function setStatus(text) {
  generateStatus.textContent = text;
}

function disposeObject(object) {
  if (!object) return;

  object.traverse?.((child) => {
    if (child.geometry) child.geometry.dispose();
    if (child.material) {
      if (Array.isArray(child.material)) {
        child.material.forEach((m) => m.dispose());
      } else {
        child.material.dispose?.();
      }
    }
  });

  if (object.parent) object.parent.remove(object);
}

function cleanGeometry(geometry) {
  const g = geometry.clone();

  // three-bvh-csg expects indexed geometry.
  // STLLoader often returns non-indexed triangle soup, so create a simple
  // sequential index instead of leaving geometry.index undefined.
  const position = g.getAttribute("position");

  if (!position) {
    throw new Error("Geometry has no position attribute.");
  }

  if (!g.index) {
    const indices = [];

    for (let i = 0; i < position.count; i++) {
      indices.push(i);
    }

    g.setIndex(indices);
  }

  g.clearGroups();
  g.addGroup(0, g.index.count, 0);

  g.deleteAttribute("normal");
  g.computeVertexNormals();
  g.computeBoundingBox();
  g.computeBoundingSphere();

  return g;
}

function getScaledGeometry() {
  if (!originalGeometry) return null;

  const scale = Number(scaleSlider.value);
  const geometry = cleanGeometry(originalGeometry);
  geometry.scale(scale, scale, scale);
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();
  return geometry;
}

function makeMeshFromGeometry(geometry, material) {
  const mesh = new THREE.Mesh(geometry, material);
  mesh.updateMatrixWorld(true);
  return mesh;
}

function getBoundsInfo(geometry) {
  geometry.computeBoundingBox();
  const box = geometry.boundingBox;
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);
  return { box, size, center };
}

function updateStats(geometry) {
  const { box, size } = getBoundsInfo(geometry);
  const faces = geometry.attributes.position.count / 3;

  stats.innerHTML = `
    <span>Bounds: ${size.x.toFixed(2)} × ${size.y.toFixed(2)} × ${size.z.toFixed(2)} mm</span>
    <span>Z range: ${box.min.z.toFixed(2)} to ${box.max.z.toFixed(2)}</span>
    <span>Faces: ${Math.round(faces).toLocaleString()}</span>
  `;
}

function resetCameraToGeometry(geometry) {
  const { size, center } = getBoundsInfo(geometry);
  const maxDim = Math.max(size.x, size.y, size.z, 20);
  camera.position.set(center.x + maxDim * 1.4, center.y - maxDim * 1.8, center.z + maxDim * 1.2);
  camera.near = Math.max(maxDim / 1000, 0.01);
  camera.far = maxDim * 100;
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
}

function downloadTextAsFile(text, filename, linkElement) {
  const blob = new Blob([text], { type: "model/stl" });
  const url = URL.createObjectURL(blob);

  if (linkElement.dataset.url) {
    URL.revokeObjectURL(linkElement.dataset.url);
  }

  linkElement.href = url;
  linkElement.download = filename;
  linkElement.dataset.url = url;
  linkElement.classList.remove("disabled");
}

function resizeRenderer() {
  const width = viewer.clientWidth;
  const height = viewer.clientHeight;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

window.addEventListener("resize", resizeRenderer);
resizeRenderer();

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

animate();

// ---------- VISUAL HELPERS ----------

function makeSlicePlane(width, height, z, center) {
  const planeGeometry = new THREE.PlaneGeometry(width, height);
  const plane = new THREE.Mesh(planeGeometry, materialPlane);
  plane.position.set(center.x, center.y, z);
  return plane;
}

function makeMXReferenceCube(center, z) {
  const boxGeometry = new THREE.BoxGeometry(19, 19, 19);
  const edges = new THREE.EdgesGeometry(boxGeometry);
  const line = new THREE.LineSegments(edges, materialMX);
  line.position.set(center.x, center.y, z);
  return line;
}

function updateWarning(box, sliceZ) {
  warnings.innerHTML = "";

  const topSpace = box.max.z - sliceZ;
  const bottomSpace = sliceZ - box.min.z;

  const topNeeded = Math.max(HOUSING_DEPTH, CROSS_DEPTH);
  const bottomNeeded = Math.max(BOTTOM_CAVITY_DEPTH, HOLE_DEPTH);

  if (topSpace < topNeeded) {
    const div = document.createElement("div");
    div.className = "warning";
    div.textContent = "Slice plane may be too high. The top cavity may cut through the model.";
    warnings.appendChild(div);
  }

  if (bottomSpace < bottomNeeded) {
    const div = document.createElement("div");
    div.className = "warning";
    div.textContent = "Slice plane may be too low. The bottom cavity or pin holes may cut through the model.";
    warnings.appendChild(div);
  }
}

function refreshPreview({ resetCamera = false } = {}) {
  if (!originalGeometry) return;

  disposeObject(previewMesh);
  disposeObject(slicePlaneMesh);
  disposeObject(mxReference);
  disposeObject(finalGroup);

  finalGroup = null;

  const geometry = getScaledGeometry();
  const { box, size, center } = getBoundsInfo(geometry);
  currentBounds = { box, size, center };

  const sliceZ = Number(sliceSlider.value);

  previewMesh = makeMeshFromGeometry(geometry, materialPreview);
  scene.add(previewMesh);

  const planeSize = Math.max(size.x, size.y, 20) * 1.35;
  slicePlaneMesh = makeSlicePlane(planeSize, planeSize, sliceZ, center);
  scene.add(slicePlaneMesh);

  mxReference = makeMXReferenceCube(center, sliceZ);
  scene.add(mxReference);

  updateWarning(box, sliceZ);
  updateStats(geometry);

  if (resetCamera) {
    resetCameraToGeometry(geometry);
  }
}

// ---------- CSG GEOMETRY HELPERS ----------

function makeBrushBox(x, y, z, center) {
  const geometry = new THREE.BoxGeometry(x, y, z);
  geometry.translate(center.x, center.y, center.z);

  const brush = new Brush(geometry, new THREE.MeshStandardMaterial());
  brush.updateMatrixWorld(true);
  return brush;
}

function makeBrushCylinder(diameter, height, center) {
  const geometry = new THREE.CylinderGeometry(diameter / 2, diameter / 2, height, 64, 1, false);
  // Three.js cylinders are along Y by default. Rotate so cylinder axis is Z.
  geometry.rotateX(Math.PI / 2);
  geometry.translate(center.x, center.y, center.z);

  const brush = new Brush(geometry, new THREE.MeshStandardMaterial());
  brush.updateMatrixWorld(true);
  return brush;
}

function meshToBrush(mesh) {
  const brush = new Brush(mesh.geometry.clone(), new THREE.MeshStandardMaterial());
  brush.position.copy(mesh.position);
  brush.rotation.copy(mesh.rotation);
  brush.scale.copy(mesh.scale);
  brush.updateMatrixWorld(true);
  return brush;
}

function resultToMesh(result, material) {
  const geometry = cleanGeometry(result.geometry);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.updateMatrixWorld(true);
  return mesh;
}

function subtractMany(evaluator, baseBrush, cutters) {
  let result = baseBrush;

  for (const cutter of cutters) {
    result = evaluator.evaluate(result, cutter, SUBTRACTION);
    result.updateMatrixWorld(true);
  }

  return result;
}

// ---------- MAIN CSG GENERATION ----------

async function generateClickerParts() {
  if (!originalGeometry) return;

  generateButton.disabled = true;
  setStatus("Generating... this can take a bit for large STLs.");

  // Give the browser time to repaint the status before heavy CSG.
  await new Promise((resolve) => setTimeout(resolve, 50));

  try {
    disposeObject(finalGroup);
    finalGroup = null;

    const geometry = getScaledGeometry();
    const sourceMesh = makeMeshFromGeometry(geometry, new THREE.MeshStandardMaterial());
    const sourceBrush = meshToBrush(sourceMesh);

    const { box, size, center } = getBoundsInfo(geometry);
    const sliceZ = Number(sliceSlider.value);
    const evaluator = new Evaluator();

    // Big intersection boxes to split the model into top and bottom.
    const pad = Math.max(size.x, size.y, size.z, 50) * 3;

    const topHeight = Math.max(box.max.z - sliceZ + pad, 1);
    const bottomHeight = Math.max(sliceZ - box.min.z + pad, 1);

    const topBox = makeBrushBox(
      size.x + pad,
      size.y + pad,
      topHeight,
      new THREE.Vector3(center.x, center.y, sliceZ + topHeight / 2)
    );

    const bottomBox = makeBrushBox(
      size.x + pad,
      size.y + pad,
      bottomHeight,
      new THREE.Vector3(center.x, center.y, sliceZ - bottomHeight / 2)
    );

    let top = evaluator.evaluate(sourceBrush, topBox, INTERSECTION);
    let bottom = evaluator.evaluate(sourceBrush, bottomBox, INTERSECTION);

    top.updateMatrixWorld(true);
    bottom.updateMatrixWorld(true);

    // Top housing side cutters.
    const topCutZ = sliceZ + HOUSING_DEPTH / 2;
    const sideWidth = (HOUSING_SIZE - CENTER_BOSS_SIZE) / 2;

    const topCutters = [
      makeBrushBox(
        sideWidth,
        HOUSING_SIZE,
        HOUSING_DEPTH,
        new THREE.Vector3(center.x - CENTER_BOSS_SIZE / 2 - sideWidth / 2, center.y, topCutZ)
      ),
      makeBrushBox(
        sideWidth,
        HOUSING_SIZE,
        HOUSING_DEPTH,
        new THREE.Vector3(center.x + CENTER_BOSS_SIZE / 2 + sideWidth / 2, center.y, topCutZ)
      ),
      makeBrushBox(
        CENTER_BOSS_SIZE,
        sideWidth,
        HOUSING_DEPTH,
        new THREE.Vector3(center.x, center.y + CENTER_BOSS_SIZE / 2 + sideWidth / 2, topCutZ)
      ),
      makeBrushBox(
        CENTER_BOSS_SIZE,
        sideWidth,
        HOUSING_DEPTH,
        new THREE.Vector3(center.x, center.y - CENTER_BOSS_SIZE / 2 - sideWidth / 2, topCutZ)
      ),
    ];

    const crossZ = sliceZ + CROSS_DEPTH / 2;

    topCutters.push(
      makeBrushBox(
        CROSS_ARM,
        CROSS_WIDTH,
        CROSS_DEPTH,
        new THREE.Vector3(center.x, center.y, crossZ)
      )
    );

    topCutters.push(
      makeBrushBox(
        CROSS_WIDTH,
        CROSS_ARM,
        CROSS_DEPTH,
        new THREE.Vector3(center.x, center.y, crossZ)
      )
    );

    top = subtractMany(evaluator, top, topCutters);

    // Bottom cavity and pins.
    const bottomCavityZ = sliceZ - BOTTOM_CAVITY_DEPTH / 2;
    const bottomCutters = [
      makeBrushBox(
        BOTTOM_CAVITY_SIZE,
        BOTTOM_CAVITY_SIZE,
        BOTTOM_CAVITY_DEPTH,
        new THREE.Vector3(center.x, center.y, bottomCavityZ)
      )
    ];

    const holeZ = sliceZ - HOLE_DEPTH / 2;

    for (const [x, y, dia] of PIN_HOLES) {
      bottomCutters.push(
        makeBrushCylinder(
          dia,
          HOLE_DEPTH,
          new THREE.Vector3(center.x + x, center.y + y, holeZ)
        )
      );
    }

    bottom = subtractMany(evaluator, bottom, bottomCutters);

    const topMesh = resultToMesh(top, materialTop);
    const bottomMesh = resultToMesh(bottom, materialBottom);

    // Show final preview, with top lifted like the Python version.
    disposeObject(previewMesh);
    disposeObject(slicePlaneMesh);
    disposeObject(mxReference);

    finalGroup = new THREE.Group();
    topMesh.position.z += 8;
    finalGroup.add(topMesh);
    finalGroup.add(bottomMesh);
    scene.add(finalGroup);

    const exporter = new STLExporter();

    const topSTL = exporter.parse(topMesh, { binary: false });
    const bottomSTL = exporter.parse(bottomMesh, { binary: false });

    downloadTextAsFile(topSTL, TOP_OUTPUT, downloadTop);
    downloadTextAsFile(bottomSTL, BOTTOM_OUTPUT, downloadBottom);

    const topFaces = topMesh.geometry.attributes.position.count / 3;
    const bottomFaces = bottomMesh.geometry.attributes.position.count / 3;

    setStatus(`Done. Top faces: ${Math.round(topFaces).toLocaleString()} | Bottom faces: ${Math.round(bottomFaces).toLocaleString()}`);

  } catch (error) {
    console.error(error);
    setStatus(`Generation failed: ${error.message || error}`);
    alert("Generation failed. Try a simpler/watertight STL, or move the slice plane. Check the browser console for details.");
  } finally {
    generateButton.disabled = false;
  }
}

// ---------- EVENTS ----------

fileInput.addEventListener("change", async (event) => {
  const file = event.target.files?.[0];

  if (!file) return;

  fileStatus.textContent = `Loading ${file.name}...`;
  setStatus("Loading STL...");

  const arrayBuffer = await file.arrayBuffer();
  const loader = new STLLoader();

  try {
    const loadedGeometry = loader.parse(arrayBuffer);
    originalGeometry = cleanGeometry(loadedGeometry);

    const scaledGeometry = getScaledGeometry();
    const { box } = getBoundsInfo(scaledGeometry);

    sliceSlider.disabled = false;
    sliceSlider.min = box.min.z;
    sliceSlider.max = box.max.z;
    sliceSlider.step = Math.max((box.max.z - box.min.z) / 300, 0.001);
    sliceSlider.value = (box.min.z + box.max.z) / 2;

    sliceValue.textContent = Number(sliceSlider.value).toFixed(2);
    scaleValue.textContent = `${Number(scaleSlider.value).toFixed(2)}x`;

    generateButton.disabled = false;
    downloadTop.classList.add("disabled");
    downloadBottom.classList.add("disabled");

    fileStatus.textContent = `Loaded: ${file.name}`;
    setStatus("Ready.");
    refreshPreview({ resetCamera: true });

  } catch (error) {
    console.error(error);
    fileStatus.textContent = "Failed to load STL.";
    setStatus(`Load failed: ${error.message || error}`);
  }
});

scaleSlider.addEventListener("input", () => {
  scaleValue.textContent = `${Number(scaleSlider.value).toFixed(2)}x`;

  if (!originalGeometry) return;

  const scaledGeometry = getScaledGeometry();
  const { box } = getBoundsInfo(scaledGeometry);

  const oldRatio = (
    (Number(sliceSlider.value) - Number(sliceSlider.min)) /
    (Number(sliceSlider.max) - Number(sliceSlider.min) || 1)
  );

  sliceSlider.min = box.min.z;
  sliceSlider.max = box.max.z;
  sliceSlider.step = Math.max((box.max.z - box.min.z) / 300, 0.001);
  sliceSlider.value = box.min.z + oldRatio * (box.max.z - box.min.z);
  sliceValue.textContent = Number(sliceSlider.value).toFixed(2);

  refreshPreview();
});

sliceSlider.addEventListener("input", () => {
  sliceValue.textContent = Number(sliceSlider.value).toFixed(2);
  refreshPreview();
});

generateButton.addEventListener("click", generateClickerParts);

resetCameraButton.addEventListener("click", () => {
  const geometry = getScaledGeometry();
  if (geometry) resetCameraToGeometry(geometry);
});
