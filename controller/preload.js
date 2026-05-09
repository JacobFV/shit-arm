const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('shitArm', {
  readState: () => ipcRenderer.invoke('read-controller-state')
});

