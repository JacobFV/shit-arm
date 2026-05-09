const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const webcam = document.getElementById('webcam');
const connectionStatus = document.getElementById('connectionStatus');
const webcamStatus = document.getElementById('webcamStatus');

const WS_URL = 'ws://127.0.0.1:8765/ws';

let latestState = null;

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

function renderOverlay(state) {
  drawWorkspace(state);
}

function drawWorkspace(state) {
  resizeCanvasToViewport();
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

function resizeCanvasToViewport() {
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width));
  const height = Math.max(1, Math.floor(rect.height));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
}

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
        latestState = msg;
        renderOverlay(msg);
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
