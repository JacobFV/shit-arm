const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const armCanvas = document.getElementById('armCanvas');
const armCtx = armCanvas.getContext('2d');
const webcam = document.getElementById('webcam');
const connectionStatus = document.getElementById('connectionStatus');
const webcamStatus = document.getElementById('webcamStatus');

const WS_URL = 'ws://127.0.0.1:8765/ws';

let latestState = null;
let activeView = 'workspace';

const orbit = {
  yaw: -0.72,
  pitch: 0.58,
  distance: 1.85,
  dragging: false,
  lastX: 0,
  lastY: 0
};

const els = {
  webcamStatus: document.getElementById('webcamStatus'),
  workspaceView: document.getElementById('workspaceView'),
  simulationView: document.getElementById('simulationView'),
  tabs: Array.from(document.querySelectorAll('.tab')),
  proprioKv: document.getElementById('proprioKv'),
  jointBars: document.getElementById('jointBars')
};

function number(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Number(value).toFixed(3);
}

function renderState(state) {
  latestState = state;
  drawWorkspace(state);
  drawSimulation(state);
  renderProprioception(state);
}

function drawWorkspace(state) {
  resizeCanvasToElement(canvas);
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const camera = state.camera || {};
  const sx = camera.width ? canvas.width / camera.width : 1;
  const sy = camera.height ? canvas.height / camera.height : 1;

  drawGrid();

  const gripper = state.gripper_pixel;
  if (gripper) {
    drawCross(gripper.x * sx, gripper.y * sy, '#f3c969', 'gripper');
  }

  for (const track of state.perception?.tracks || []) {
    const bbox = track.bbox_xywh;
    const selected = track.track_id === state.perception?.selected_track_id;
    if (bbox) {
      ctx.strokeStyle = selected ? '#62d6a8' : '#7da7ff';
      ctx.lineWidth = selected ? 3 : 2;
      ctx.strokeRect(bbox[0] * sx, bbox[1] * sy, bbox[2] * sx, bbox[3] * sy);
    }
    if (track.pixel) {
      drawCross(track.pixel.x * sx, track.pixel.y * sy, selected ? '#62d6a8' : '#7da7ff', `#${track.track_id}`);
    }
  }
}

function renderProprioception(state) {
  const joints = state.robot?.joints || [];
  const pose = state.pose;
  els.proprioKv.innerHTML = '';
  const rows = [
    ['Robot', state.robot?.connected ? 'connected' : 'offline'],
    ['Gripper', number(state.robot?.gripper)],
    ['End effector', pose ? `${number(pose.x)}, ${number(pose.y)}, ${number(pose.z)}` : '-'],
    ['Joint count', String(joints.length)]
  ];
  for (const [key, value] of rows) {
    const row = document.createElement('div');
    row.innerHTML = `<dt>${key}</dt><dd>${value}</dd>`;
    els.proprioKv.appendChild(row);
  }

  els.jointBars.innerHTML = '';
  joints.forEach((joint, index) => {
    const pct = normalize(joint, -Math.PI, Math.PI);
    const bar = document.createElement('div');
    bar.className = 'joint-row';
    bar.innerHTML = `
      <div class="joint-label"><span>J${index + 1}</span><span>${number(joint)}</span></div>
      <div class="joint-track">
        <div class="joint-fill" style="width: ${pct}%"></div>
      </div>
      <div class="joint-limits"><span>${number(-Math.PI)}</span><span>${number(Math.PI)}</span></div>
    `;
    els.jointBars.appendChild(bar);
  });
}

function drawSimulation(state) {
  resizeCanvasToElement(armCanvas);
  armCtx.clearRect(0, 0, armCanvas.width, armCanvas.height);
  drawSimBackground3d();

  const joints = state.robot?.joints || [];
  const points = armPoints3d(joints);

  if (points.length > 1) {
    drawArmChain3d(points, '#62d6a8', 1, true);
  }

  const ee = points[points.length - 1];
  if (ee) {
    const grip = Number(state.robot?.gripper ?? 0);
    drawGripper3d(ee, joints, grip);
  }

  drawPoseReadout(state);
}

function drawSimBackground3d() {
  armCtx.fillStyle = '#0d0f13';
  armCtx.fillRect(0, 0, armCanvas.width, armCanvas.height);

  for (let x = -0.55; x <= 0.55; x += 0.11) {
    drawLine3d({ x, y: -0.55, z: 0 }, { x, y: 0.75, z: 0 }, '#202833', 1, 1);
  }
  for (let y = -0.55; y <= 0.75; y += 0.11) {
    drawLine3d({ x: -0.55, y, z: 0 }, { x: 0.55, y, z: 0 }, '#202833', 1, 1);
  }
  drawLine3d({ x: -0.6, y: 0, z: 0 }, { x: 0.6, y: 0, z: 0 }, '#8c3b3b', 2, 0.8);
  drawLine3d({ x: 0, y: -0.6, z: 0 }, { x: 0, y: 0.8, z: 0 }, '#2d6b4f', 2, 0.8);
  drawLine3d({ x: 0, y: 0, z: 0 }, { x: 0, y: 0, z: 0.5 }, '#355c9a', 2, 0.8);
}

function armPoints3d(joints) {
  const values = Array.from({ length: 6 }, (_item, index) => Number(joints[index] || 0));
  const baseYaw = values[0];
  const shoulder = values[1];
  const elbow = values[2];
  const wrist = values[4];
  const lengths = [0.12, 0.18, 0.16, 0.1, 0.075, 0.055];
  const points = [{ x: 0, y: 0, z: 0.035 }];
  let reach = 0;
  let z = 0.035;
  let pitch = -0.2 + shoulder * 0.45;

  z += lengths[0];
  points.push(radialPoint(baseYaw, reach, z));

  reach += Math.cos(pitch) * lengths[1];
  z += Math.sin(pitch) * lengths[1];
  points.push(radialPoint(baseYaw, reach, z));

  pitch += elbow * 0.35;
  reach += Math.cos(pitch) * lengths[2];
  z += Math.sin(pitch) * lengths[2];
  points.push(radialPoint(baseYaw, reach, z));

  pitch += values[3] * 0.12;
  reach += Math.cos(pitch) * lengths[3];
  z += Math.sin(pitch) * lengths[3];
  points.push(radialPoint(baseYaw + values[3] * 0.16, reach, z));

  pitch += wrist * 0.25;
  reach += Math.cos(pitch) * lengths[4];
  z += Math.sin(pitch) * lengths[4];
  points.push(radialPoint(baseYaw + values[5] * 0.12, reach, z));

  reach += Math.cos(pitch) * lengths[5];
  z += Math.sin(pitch) * lengths[5];
  points.push(radialPoint(baseYaw + values[5] * 0.12, reach, z));
  return points;
}

function radialPoint(yaw, reach, z) {
  return {
    x: Math.sin(yaw) * reach,
    y: Math.cos(yaw) * reach + 0.12,
    z
  };
}

function drawArmChain3d(points, color, alpha, solid) {
  armCtx.save();
  armCtx.globalAlpha = alpha;
  for (let index = 0; index < points.length - 1; index += 1) {
    drawLine3d(points[index], points[index + 1], color, solid ? 12 : 6, 1);
  }
  for (const point of points) {
    const projected = project3d(point);
    if (!projected.visible) continue;
    armCtx.fillStyle = '#101820';
    armCtx.strokeStyle = color;
    armCtx.lineWidth = solid ? 3 : 2;
    armCtx.beginPath();
    armCtx.arc(projected.x, projected.y, (solid ? 9 : 6) * projected.scale, 0, Math.PI * 2);
    armCtx.fill();
    armCtx.stroke();
  }
  armCtx.restore();
}

function drawGripper3d(point, joints, grip) {
  const yaw = Number(joints[0] || 0);
  const open = 0.018 + Math.max(0, Math.min(1, grip)) * 0.035;
  const forward = { x: Math.sin(yaw) * 0.055, y: Math.cos(yaw) * 0.055, z: 0 };
  const side = { x: Math.cos(yaw) * open, y: -Math.sin(yaw) * open, z: 0.012 };
  drawLine3d(point, add3(point, add3(forward, side)), '#f3c969', 4, 1);
  drawLine3d(point, add3(point, add3(forward, scale3(side, -1))), '#f3c969', 4, 1);
}

function drawLine3d(a, b, color, width, alpha) {
  const pa = project3d(a);
  const pb = project3d(b);
  if (!pa.visible || !pb.visible) return;
  armCtx.save();
  armCtx.globalAlpha = alpha;
  armCtx.strokeStyle = color;
  armCtx.lineWidth = Math.max(1, width * Math.min(pa.scale, pb.scale));
  armCtx.lineCap = 'round';
  armCtx.beginPath();
  armCtx.moveTo(pa.x, pa.y);
  armCtx.lineTo(pb.x, pb.y);
  armCtx.stroke();
  armCtx.restore();
}

function project3d(point) {
  const cy = Math.cos(orbit.yaw);
  const sy = Math.sin(orbit.yaw);
  const cp = Math.cos(orbit.pitch);
  const sp = Math.sin(orbit.pitch);
  const x1 = point.x * cy - point.y * sy;
  const y1 = point.x * sy + point.y * cy;
  const z1 = point.z;
  const y2 = y1 * cp - z1 * sp;
  const z2 = y1 * sp + z1 * cp;
  const depth = orbit.distance + y2;
  if (depth <= 0.08) {
    return { visible: false, x: 0, y: 0, scale: 1 };
  }
  const scale = Math.min(2.2, Math.max(0.45, 1.15 / depth));
  const viewportScale = Math.min(armCanvas.width, armCanvas.height) * 1.15;
  return {
    visible: true,
    x: armCanvas.width * 0.5 + x1 * viewportScale * scale,
    y: armCanvas.height * 0.58 - z2 * viewportScale * scale,
    scale
  };
}

function add3(a, b) {
  return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z };
}

function scale3(point, scalar) {
  return { x: point.x * scalar, y: point.y * scalar, z: point.z * scalar };
}

function drawPoseReadout(state) {
  const pose = state.pose;
  armCtx.fillStyle = '#d7dee8';
  armCtx.font = '13px system-ui';
  armCtx.fillText(`mode ${state.mode || '-'}`, 24, 32);
  armCtx.fillText(`pose ${pose ? `${number(pose.x)} ${number(pose.y)} ${number(pose.z)}` : '-'}`, 24, 54);
  armCtx.fillStyle = '#62d6a8';
  armCtx.fillText('robot self state', 24, 76);
  armCtx.fillStyle = '#8994a5';
  armCtx.fillText(`orbit yaw ${number(orbit.yaw)} pitch ${number(orbit.pitch)} zoom ${number(orbit.distance)}`, 24, 98);
}

function drawGrid() {
  ctx.strokeStyle = '#202833';
  ctx.lineWidth = 1;
  for (let x = 0; x <= canvas.width; x += 80) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
  }
  for (let y = 0; y <= canvas.height; y += 80) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(canvas.width, y);
    ctx.stroke();
  }
}

function drawCross(x, y, color, label) {
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(x - 8, y);
  ctx.lineTo(x + 8, y);
  ctx.moveTo(x, y - 8);
  ctx.lineTo(x, y + 8);
  ctx.stroke();
  ctx.font = '12px system-ui';
  ctx.fillText(label, x + 10, y - 10);
}

function normalize(value, low, high) {
  if (!Number.isFinite(low) || !Number.isFinite(high) || high === low) return 50;
  return Math.max(0, Math.min(100, ((Number(value) - low) / (high - low)) * 100));
}

function resizeCanvasToElement(target) {
  const rect = target.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width));
  const height = Math.max(1, Math.floor(rect.height));
  if (target.width !== width || target.height !== height) {
    target.width = width;
    target.height = height;
  }
}

function setActiveView(view) {
  activeView = view;
  els.workspaceView.classList.toggle('active', view === 'workspace');
  els.simulationView.classList.toggle('active', view === 'simulation');
  for (const tab of els.tabs) {
    const selected = tab.dataset.view === view;
    tab.classList.toggle('active', selected);
    tab.setAttribute('aria-selected', String(selected));
  }
  if (latestState) {
    drawWorkspace(latestState);
    drawSimulation(latestState);
  }
}

for (const tab of els.tabs) {
  tab.addEventListener('click', () => setActiveView(tab.dataset.view));
}

armCanvas.addEventListener('pointerdown', (event) => {
  orbit.dragging = true;
  orbit.lastX = event.clientX;
  orbit.lastY = event.clientY;
  armCanvas.setPointerCapture(event.pointerId);
});

armCanvas.addEventListener('pointermove', (event) => {
  if (!orbit.dragging) return;
  const dx = event.clientX - orbit.lastX;
  const dy = event.clientY - orbit.lastY;
  orbit.lastX = event.clientX;
  orbit.lastY = event.clientY;
  orbit.yaw += dx * 0.008;
  orbit.pitch = Math.max(-1.15, Math.min(1.25, orbit.pitch + dy * 0.008));
  if (latestState) drawSimulation(latestState);
});

armCanvas.addEventListener('pointerup', (event) => {
  orbit.dragging = false;
  if (armCanvas.hasPointerCapture(event.pointerId)) {
    armCanvas.releasePointerCapture(event.pointerId);
  }
});

armCanvas.addEventListener('pointercancel', () => {
  orbit.dragging = false;
});

armCanvas.addEventListener('wheel', (event) => {
  event.preventDefault();
  orbit.distance = Math.max(0.85, Math.min(3.2, orbit.distance + event.deltaY * 0.0015));
  if (latestState) drawSimulation(latestState);
}, { passive: false });

async function startWebcam() {
  if (!navigator.mediaDevices?.getUserMedia) {
    webcamStatus.textContent = 'camera unavailable';
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 1280 },
        height: { ideal: 720 }
      },
      audio: false
    });
    webcam.srcObject = stream;
    webcamStatus.textContent = 'webcam live';
  } catch (error) {
    webcamStatus.textContent = `webcam blocked: ${error.message}`;
  }
}

function connectWebSocket() {
  const ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    connectionStatus.textContent = 'connected';
    connectionStatus.className = 'connection-status connected';
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === 'state') {
        renderState(msg);
      }
    } catch (e) {
      // ignore parse errors
    }
  };

  ws.onclose = () => {
    connectionStatus.textContent = 'disconnected (reconnecting...)';
    connectionStatus.className = 'connection-status';
    setTimeout(connectWebSocket, 2000);
  };

  ws.onerror = () => {
    ws.close();
  };
}

startWebcam();
connectWebSocket();
