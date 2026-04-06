const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  selectFolder: () => ipcRenderer.invoke('select-folder'),
  zipFolder: (folderPath) => ipcRenderer.invoke('zip-folder', folderPath),
  selectFile: () => ipcRenderer.invoke('select-file'),
  saveFile: (defaultName) => ipcRenderer.invoke('save-file', defaultName),
  onZipProgress: (callback) => ipcRenderer.on('zip-progress', (event, percent) => callback(percent))
});
