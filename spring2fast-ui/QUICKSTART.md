# 🚀 Quick Start Guide - Spring2Fast UI

Get up and running in 5 minutes!

## Step 1: Install Dependencies

```bash
cd spring2fast-ui
npm install
```

This will install all required packages including:
- React, React Router, Axios
- Electron
- TailwindCSS
- Lucide Icons
- Archiver (for folder zipping)

## Step 2: Start the Backend

In a separate terminal, start the Spring2Fast backend:

```bash
cd spring2fast

# Activate virtual environment
.venv\Scripts\activate  # Windows
# or
source .venv/bin/activate  # Mac/Linux

# Run the backend
uvicorn app.main:app --reload
```

The backend should be running on http://localhost:8000

Verify by visiting: http://localhost:8000/docs

## Step 3: Start the Electron App

```bash
cd spring2fast-ui
npm run electron:dev
```

This will:
1. Start Vite dev server on port 5173
2. Launch the Electron desktop app
3. Enable hot reload for development

## Step 4: Create Your First Migration

1. **Choose a method**:
   - GitHub: Enter a Spring Boot repo URL
   - Local Folder: Click "Browse" to select a folder
   - Upload ZIP: Drag & drop a ZIP file

2. **Click "Start Migration"**

3. **Watch the progress** in real-time!

## What You'll See

### Home Page
- Three migration method options
- Clean, intuitive interface
- Info box explaining the process

### Job Status Page (8 Tabs)
1. **Pipeline**: Visual flow of 10 agent stages
2. **Statistics**: 6 key metrics
3. **Components**: Discovered Spring Boot components
4. **Tech Mapping**: Java → Python mappings
5. **Business Rules**: Extracted business logic
6. **Code Preview**: Browse generated files
7. **Artifacts**: View markdown documents
8. **Logs**: Real-time migration logs

### When Complete
- Download button appears
- Get a complete FastAPI project as ZIP
- Includes models, routers, services, Dockerfile, requirements.txt

## Troubleshooting

### Backend not connecting?
- Check if backend is running: http://localhost:8000/docs
- Verify API URL in Settings (should be http://localhost:8000)

### Electron won't start?
- Make sure you're in `spring2fast-ui` directory
- Run `npm install` again
- Check that port 5173 is available

### Folder selection not working?
- This only works in Electron app (not browser)
- Make sure you have read permissions

## Next Steps

- **Explore Features**: Check out FEATURES.md for complete feature list
- **Read Documentation**: See README.md for detailed info
- **Build for Production**: Run `npm run electron:build`

## Tips

- **Hot Reload**: Changes to React components reload automatically
- **DevTools**: Press F12 to open Chrome DevTools
- **Multiple Jobs**: You can track multiple migrations in History

## Need Help?

- Check the logs in the Logs tab
- Look for error messages in the terminal
- Verify backend is running and accessible

---

**Happy Migrating! 🎉**
