const { app, BrowserWindow } = require('electron')
const path = require('path')

function createWindow () {
  const win = new BrowserWindow({
    width: 800,
    height: 600,
    resizable: true,   // Enable window resizing
    minWidth: 400,     // Minimum usable width
    minHeight: 300,    // Minimum usable height
    maxWidth: 1600,    // Maximum width
    maxHeight: 1200,   // Maximum height
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false
      // offscreen: true, // Enables offscreen rendering
    },
    transparent: true, // Set to true for transparency
    frame: false,      // Remove window frame
    backgroundColor: '#00000000', // Fully transparent background
    hasShadow: true,
    visualEffectState: 'active'
  })

  win.loadFile('index.html')

  // Open DevTools by default
  // win.webContents.openDevTools()
  
  win.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.error(`Failed to load: ${errorDescription} (${errorCode})`);
  });

  // Make sure the window is always on top
  win.setAlwaysOnTop(true, 'floating')

  // Hide the window from the taskbar
  win.setSkipTaskbar(true)

  win.once('ready-to-show', () => {
    win.show()
  })

  // Add this line to focus the window
  win.focus()
}

app.whenReady().then(() => {
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// Add these lines to handle any unhandled exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error)
})

// Add these lines to log when the app is ready
app.on('ready', () => {
  console.log('App is ready')
})
