# Spring2Fast Desktop UI

Electron + React desktop application for Spring2Fast - Java Spring Boot to Python FastAPI migration tool.

## 🎯 Features

### Phase 1: Essential Features ✅
- ✅ **Real-time Agent Pipeline Visualization** - Watch your migration progress through 10 stages
- ✅ **Artifact Viewer & Explorer** - Browse generated markdown artifacts with search
- ✅ **Logs & Debug Viewer** - Filter, search, and download migration logs
- ✅ **Migration Statistics Dashboard** - 6 key metrics at a glance

### Phase 2: Advanced Features ✅
- ✅ **Component Inventory Visualization** - Explore controllers, services, entities, DTOs
- ✅ **Technology Mapping Matrix** - See Java → Python mappings with pip commands
- ✅ **Generated Code Preview** - Browse and preview all generated Python files
- ✅ **Business Rules Tracker** - Track extracted business logic with verification status

### Core Capabilities
- 🚀 **GitHub Integration** - Clone and migrate from GitHub repositories
- 📁 **Local Folder Support** - Select local Spring Boot projects with native picker
- 📦 **ZIP Upload** - Upload zipped projects with drag-and-drop
- 📊 **Real-time Progress** - Live updates every 3 seconds
- 💾 **Job History** - View and manage past migrations
- ⚙️ **Configurable Backend** - Connect to local or remote API

## Prerequisites

- Node.js 18+ and npm
- Spring2Fast backend running (default: http://localhost:8000)

## Installation

```bash
cd spring2fast-ui
npm install
npm install archiver  # Required for folder zipping
```

## Development

Run in development mode with hot reload:

```bash
npm run electron:dev
```

This will:
1. Start Vite dev server on port 5173
2. Launch Electron app
3. Enable hot module replacement

## Building

Build the desktop app for your platform:

```bash
npm run electron:build
```

Output will be in the `release/` directory.

Builds for:
- **Windows**: NSIS installer
- **macOS**: DMG
- **Linux**: AppImage

## Project Structure

```
spring2fast-ui/
├── electron/              # Electron main process
│   ├── main.js           # Main process entry
│   └── preload.js        # Preload script (IPC bridge)
├── src/
│   ├── components/       # React components
│   │   ├── PipelineVisualization.jsx
│   │   ├── StatsDashboard.jsx
│   │   ├── ArtifactViewer.jsx
│   │   ├── LogsViewer.jsx
│   │   ├── ComponentVisualization.jsx
│   │   ├── TechnologyMapping.jsx
│   │   ├── CodePreview.jsx
│   │   ├── BusinessRulesTracker.jsx
│   │   ├── GitHubForm.jsx
│   │   ├── LocalFolderForm.jsx
│   │   ├── UploadForm.jsx
│   │   └── Layout.jsx
│   ├── pages/            # Page components
│   │   ├── HomePage.jsx
│   │   ├── JobStatusPage.jsx
│   │   ├── HistoryPage.jsx
│   │   └── SettingsPage.jsx
│   ├── context/          # React context
│   │   └── ApiContext.jsx
│   ├── App.jsx           # Root component
│   └── main.jsx          # React entry point
├── public/               # Static assets
├── package.json
└── README.md
```

## Configuration

The app stores the backend API URL in localStorage. You can change it in Settings.

Default: `http://localhost:8000`

## Usage Guide

### 1. Start a Migration

Choose one of three methods:
- **GitHub**: Enter repository URL and optional branch
- **Local Folder**: Click "Browse" to select a folder
- **Upload ZIP**: Drag & drop or browse for a ZIP file

### 2. Track Progress

The Job Status page shows:
- **Pipeline Tab**: Visual flow of all 10 agent stages
- **Statistics Tab**: Key metrics (files scanned, technologies detected, etc.)
- **Components Tab**: Discovered Spring Boot components
- **Tech Mapping Tab**: Java → Python technology mappings
- **Business Rules Tab**: Extracted business logic with verification
- **Code Preview Tab**: Browse generated Python files
- **Artifacts Tab**: View generated markdown documents
- **Logs Tab**: Real-time migration logs

### 3. Download Results

When migration completes, click "Download FastAPI Project" to get a ZIP containing:
- Complete FastAPI project structure
- Generated models, routers, services
- requirements.txt with dependencies
- Dockerfile and docker-compose.yml
- README with setup instructions

## Tech Stack

- **Electron** - Desktop app framework
- **React 18** - UI framework
- **Vite** - Build tool and dev server
- **TailwindCSS** - Utility-first CSS
- **Lucide React** - Icon library
- **Axios** - HTTP client
- **React Router** - Client-side routing
- **Archiver** - ZIP file creation

## Features in Detail

### Real-time Pipeline Visualization
Watch your migration progress through 10 stages:
1. Ingest Source (10%)
2. Tech Discovery (25%)
3. Business Logic Extraction (40%)
4. Component Discovery (45%)
5. Docs Research (50%)
6. Analysis (55%)
7. Planning (60%)
8. Code Generation (80%)
9. Validation (85%)
10. Assembly (100%)

### Component Visualization
Explore discovered Spring Boot components:
- **Controllers**: REST endpoints with request mappings
- **Services**: Business logic methods
- **Repositories**: Data access patterns
- **Entities**: JPA models with fields
- **DTOs**: Data transfer objects

### Technology Mapping
See how Java technologies map to Python:
- Spring Boot → FastAPI
- Spring Data JPA → SQLAlchemy
- Spring Security → FastAPI Security
- PostgreSQL → psycopg2
- Redis → redis-py
- Kafka → aiokafka

Plus one-click copy of pip install commands!

### Business Rules Tracker
Track extracted business logic:
- ✅ Verified rules
- ⚠️ Rules needing review
- ⏳ Pending verification
- Filter and search capabilities

### Code Preview
Browse generated Python files:
- File tree explorer
- Syntax-highlighted code viewer
- Copy code to clipboard
- Search across files

## Troubleshooting

### Electron app won't start
- Make sure you're in the `spring2fast-ui` directory
- Run `npm install` to ensure all dependencies are installed
- Check that port 5173 is not in use

### Backend connection failed
- Verify the backend is running on http://localhost:8000
- Check the API URL in Settings
- Try accessing http://localhost:8000/docs in your browser

### Folder selection not working
- This feature only works in the Electron app (not browser)
- Make sure you have read permissions for the folder

### ZIP upload fails
- Ensure the ZIP file contains a valid Spring Boot project
- Check file size (very large projects may take time)
- Verify the backend is running and accessible

## Development Tips

### Hot Reload
Changes to React components will hot reload automatically. Changes to Electron main process require restarting the app.

### Debugging
- React DevTools: Available in development mode
- Electron DevTools: Opens automatically in development
- Console logs: Check both browser console and terminal

### Building for Production
```bash
# Build for current platform
npm run electron:build

# Build for specific platform
npm run electron:build -- --win
npm run electron:build -- --mac
npm run electron:build -- --linux
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: [Create an issue](https://github.com/yourusername/spring2fast/issues)
- Documentation: See FEATURES.md for detailed feature list

---

**Built with ❤️ for developers migrating from Spring Boot to FastAPI**

