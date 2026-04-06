const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const archiver = require('archiver');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, '../public/icon.png')
  });

  // Load from Vite dev server in development, or from built files in production
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// IPC Handlers
ipcMain.handle('select-folder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: 'Select Spring Boot Project Folder'
  });

  if (result.canceled) {
    return { canceled: true };
  }

  return {
    canceled: false,
    folderPath: result.filePaths[0]
  };
});

ipcMain.handle('zip-folder', async (event, folderPath) => {
  return new Promise((resolve, reject) => {
    const outputPath = path.join(app.getPath('temp'), `spring2fast-${Date.now()}.zip`);
    const output = fs.createWriteStream(outputPath);
    const archive = archiver('zip', { zlib: { level: 9 } });

    output.on('close', () => {
      resolve({
        success: true,
        zipPath: outputPath,
        size: archive.pointer()
      });
    });

    archive.on('error', (err) => {
      reject(err);
    });

    archive.on('progress', (progress) => {
      const percent = Math.round((progress.fs.processedBytes / progress.fs.totalBytes) * 100);
      mainWindow.webContents.send('zip-progress', percent);
    });

    archive.pipe(output);
    archive.directory(folderPath, false);
    archive.finalize();
  });
});

ipcMain.handle('select-file', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: 'ZIP Files', extensions: ['zip'] }
    ],
    title: 'Select Spring Boot Project ZIP'
  });

  if (result.canceled) {
    return { canceled: true };
  }

  return {
    canceled: false,
    filePath: result.filePaths[0]
  };
});

ipcMain.handle('save-file', async (event, defaultName) => {
  const result = await dialog.showSaveDialog(mainWindow, {
    defaultPath: defaultName,
    filters: [
      { name: 'ZIP Files', extensions: ['zip'] }
    ],
    title: 'Save Migrated Project'
  });

  if (result.canceled) {
    return { canceled: true };
  }

  return {
    canceled: false,
    filePath: result.filePath
  };
});
