const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const webcam = document.getElementById('webcam');

const els = {
  statePath: document.getElementById('statePath'),
  safetyPill: document.getElementById('safetyPill'),
  mode: document.getElementById('mode'),
  frame: document.getElementById('frame'),
  perception: document.getElementById('perception'),
  selected: document.getElementById('selected'),
  gripperPixel: document.getElementById('gripperPixel'),
  gripperWorld: document.getElementById('gripperWorld'),
  objects: document.getElementById('objects'),
  updatedAt: document.getElementById('updatedAt'),
  webcamStatus: document.getElementById('webcamStatus')
};

function fmtPoint(point) {
  if (!point) return '-';
  return `x: ${number(point.x)}\ny: ${number(point.y)}`;
}

function fmtPose(pose) {
  if (!pose) return '-';
  return `x: ${number(pose.x)}\ny: ${number(pose.y)}\nz: ${number(pose.z)}\nroll: ${number(pose.roll)}\npitch: ${number(pose.pitch)}\nyaw: ${number(pose.yaw)}`;
}

function number(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Number(value).toFixed(3);
}

function renderState(payload) {
  const state = payload.state;
  els.statePath.textContent = payload.path;
  els.mode.textContent = state.mode || '-';
  els.frame.textContent = `${state.camera?.frame_id ?? '-'} (${state.camera?.width ?? 0}x${state.camera?.height ?? 0})`;
  els.perception.textContent = state.perception?.status || '-';
  els.selected.textContent = state.perception?.selected_track_id ?? '-';
  els.gripperPixel.textContent = fmtPoint(state.gripper?.pixel);
  els.gripperWorld.textContent = fmtPose(state.gripper?.world);
  els.updatedAt.textContent = state.timestamp ? new Date(state.timestamp * 1000).toLocaleTimeString() : '-';

  const safetyOk = Boolean(state.safety?.ok);
  els.safetyPill.textContent = safetyOk ? 'safe' : 'fault';
  els.safetyPill.className = `pill ${safetyOk ? 'ok' : 'fault'}`;

  const tracks = state.perception?.tracks || [];
  els.objects.innerHTML = '';
  for (const track of tracks) {
    const card = document.createElement('article');
    card.className = 'object-card';
    card.innerHTML = `
      <div class="object-head">
        <div class="object-title">#${track.track_id} ${track.label}</div>
        <span class="pill">${track.status}</span>
      </div>
      <pre>bin: ${track.target_bin || '-'}
confidence: ${number(track.confidence)}
score: ${number(track.score)}
pixel:
${indent(fmtPoint(track.pixel))}
world:
${indent(fmtPose(track.world))}
motion:
${indent(fmtMotion(track.motion))}</pre>
    `;
    els.objects.appendChild(card);
  }

  drawWorkspace(state);
}

function indent(text) {
  return String(text).split('\n').map((line) => `  ${line}`).join('\n');
}

function fmtMotion(motion) {
  if (!motion) return '-';
  const pd = motion.pixel_delta || [];
  const td = motion.table_delta || [];
  return `pixel dx: ${number(pd[0])}
pixel dy: ${number(pd[1])}
world dx: ${number(td[0])}
world dy: ${number(td[1])}
world dz: ${number(td[2])}
pixel speed/frame: ${number(motion.pixel_speed_per_frame)}
world speed/frame: ${number(motion.table_speed_per_frame)}
consistent: ${motion.consistent}`;
}

function drawWorkspace(state) {
  resizeCanvasToViewport();
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!webcam.srcObject) {
    ctx.fillStyle = '#111820';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  const camera = state.camera || {};
  const sx = camera.width ? canvas.width / camera.width : 1;
  const sy = camera.height ? canvas.height / camera.height : 1;

  drawGrid();

  const gripper = state.gripper?.pixel;
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

async function refresh() {
  try {
    renderState(await window.shitArm.readState());
  } catch (error) {
    els.perception.textContent = `state read failed: ${error.message}`;
  }
}

async function startWebcam() {
  if (!navigator.mediaDevices?.getUserMedia) {
    els.webcamStatus.textContent = 'camera unavailable';
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
    els.webcamStatus.textContent = 'webcam live';
  } catch (error) {
    els.webcamStatus.textContent = `webcam blocked: ${error.message}`;
  }
}

function resizeCanvasToViewport() {
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width));
  const height = Math.max(1, Math.floor(rect.height));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
}

startWebcam();
refresh();
setInterval(refresh, 500);
