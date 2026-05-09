const { app, BrowserWindow, ipcMain } = require('electron');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

const statePath = process.env.SHIT_ARM_CONTROLLER_STATE ||
  path.join(__dirname, 'controller-state.json');
const samplePath = path.join(__dirname, 'state.sample.json');
let lastGoodPayload = null;

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 980,
    minHeight: 640,
    backgroundColor: '#111317',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  win.loadFile(path.join(__dirname, 'index.html'));
}

ipcMain.handle('read-controller-state', async () => {
  const filePath = fs.existsSync(statePath) ? statePath : samplePath;
  try {
    const raw = await fs.promises.readFile(filePath, 'utf8');
    const state = JSON.parse(raw);
    const imagePath = state.camera?.frame_image_path;
    lastGoodPayload = {
      path: filePath,
      frameImageUrl: imagePath && fs.existsSync(imagePath) ? `${pathToFileURL(imagePath).href}?t=${Date.now()}` : null,
      state
    };
    return lastGoodPayload;
  } catch (error) {
    if (lastGoodPayload) {
      return {
        ...lastGoodPayload,
        stale: true,
        readError: error.message
      };
    }
    const raw = await fs.promises.readFile(samplePath, 'utf8');
    const state = JSON.parse(raw);
    return {
      path: samplePath,
      frameImageUrl: null,
      readError: error.message,
      state
    };
  }
});

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
