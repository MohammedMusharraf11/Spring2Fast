# 🏗️ Spring2Fast UI - Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Spring2Fast Desktop App                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              Electron Main Process                      │    │
│  │  ┌──────────────────────────────────────────────────┐  │    │
│  │  │  • Window Management                              │  │    │
│  │  │  • Native Dialogs (folder picker, save file)     │  │    │
│  │  │  • File System Access                            │  │    │
│  │  │  • Folder Zipping (archiver)                     │  │    │
│  │  │  • IPC Handlers                                  │  │    │
│  │  └──────────────────────────────────────────────────┘  │    │
│  └────────────────────────────────────────────────────────┘    │
│                            ↕ IPC                                │
│  ┌────────────────────────────────────────────────────────┐    │
│  │           Electron Renderer Process (React)            │    │
│  │  ┌──────────────────────────────────────────────────┐  │    │
│  │  │                  React App                        │  │    │
│  │  │  ┌────────────────────────────────────────────┐  │  │    │
│  │  │  │         Router (React Router)              │  │  │    │
│  │  │  │  ┌──────────────────────────────────────┐  │  │  │    │
│  │  │  │  │  Pages                               │  │  │  │    │
│  │  │  │  │  • HomePage                          │  │  │  │    │
│  │  │  │  │  • JobStatusPage (8 tabs)            │  │  │  │    │
│  │  │  │  │  • HistoryPage                       │  │  │  │    │
│  │  │  │  │  • SettingsPage                      │  │  │  │    │
│  │  │  │  └──────────────────────────────────────┘  │  │  │    │
│  │  │  │  ┌──────────────────────────────────────┐  │  │  │    │
│  │  │  │  │  Components (15 total)               │  │  │  │    │
│  │  │  │  │  Phase 1:                            │  │  │  │    │
│  │  │  │  │  • PipelineVisualization             │  │  │  │    │
│  │  │  │  │  • StatsDashboard                    │  │  │  │    │
│  │  │  │  │  • ArtifactViewer                    │  │  │  │    │
│  │  │  │  │  • LogsViewer                        │  │  │  │    │
│  │  │  │  │  Phase 2:                            │  │  │  │    │
│  │  │  │  │  • ComponentVisualization            │  │  │  │    │
│  │  │  │  │  • TechnologyMapping                 │  │  │  │    │
│  │  │  │  │  • CodePreview                       │  │  │  │    │
│  │  │  │  │  • BusinessRulesTracker              │  │  │  │    │
│  │  │  │  │  Core:                               │  │  │  │    │
│  │  │  │  │  • Layout, Forms, etc.               │  │  │  │    │
│  │  │  │  └──────────────────────────────────────┘  │  │  │    │
│  │  │  │  ┌──────────────────────────────────────┐  │  │  │    │
│  │  │  │  │  Context (State Management)          │  │  │  │    │
│  │  │  │  │  • ApiContext (API URL config)       │  │  │  │    │
│  │  │  │  └──────────────────────────────────────┘  │  │  │    │
│  │  │  └────────────────────────────────────────────┘  │  │    │
│  │  └──────────────────────────────────────────────────┘  │    │
│  └────────────────────────────────────────────────────────┘    │
│                            ↕ HTTP (Axios)                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Spring2Fast Backend (FastAPI)                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  API Endpoints:                                           │  │
│  │  • POST /api/v1/migrate/github                           │  │
│  │  • POST /api/v1/migrate/upload                           │  │
│  │  • GET  /api/v1/migrate/{job_id}/status                  │  │
│  │  • GET  /api/v1/migrate/{job_id}/result                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  LangGraph Agent Pipeline (10 stages):                   │  │
│  │  1. Ingest → 2. Tech Discovery → 3. Business Logic →     │  │
│  │  4. Components → 5. Docs Research → 6. Analysis →        │  │
│  │  7. Planning → 8. Code Generation → 9. Validation →      │  │
│  │  10. Assembly                                             │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### 1. Job Creation Flow

```
User Input (GitHub/Folder/ZIP)
    ↓
HomePage Component
    ↓
Form Component (GitHub/LocalFolder/Upload)
    ↓
[If Local Folder]
    → Electron IPC: selectFolder()
    → Electron Main: showOpenDialog()
    → Return folder path
    → Electron IPC: zipFolder()
    → Electron Main: archiver.zip()
    → Return ZIP path
    ↓
Axios POST to Backend
    ↓
Backend creates job
    ↓
Returns job_id
    ↓
Navigate to /job/{job_id}
```

### 2. Job Status Polling Flow

```
JobStatusPage mounts
    ↓
useEffect: Start polling (every 3s)
    ↓
Axios GET /api/v1/migrate/{job_id}/status
    ↓
Backend returns MigrationState:
    {
      job_id, status, current_step, progress_pct,
      logs, discovered_technologies, business_rules,
      generated_files, metadata, ...
    }
    ↓
Update local state
    ↓
Re-render all tabs with new data
    ↓
[If status === 'completed' or 'failed']
    → Stop polling
    ↓
[Else]
    → Continue polling after 3s
```

### 3. Component Data Flow

```
JobStatusPage (parent)
    ↓
    ├─ PipelineVisualization
    │   ← job.status, job.progress_pct
    │
    ├─ StatsDashboard
    │   ← job.metadata, job.discovered_technologies, job.business_rules
    │
    ├─ ComponentVisualization
    │   ← job.metadata.component_inventory
    │
    ├─ TechnologyMapping
    │   ← job.discovered_technologies, job.metadata.docs_research.references
    │
    ├─ BusinessRulesTracker
    │   ← job.business_rules
    │
    ├─ CodePreview
    │   ← job.generated_files
    │
    ├─ ArtifactViewer
    │   ← job_id (fetches artifacts separately)
    │
    └─ LogsViewer
        ← job.logs
```

---

## Component Architecture

### Layout Component (Wrapper)

```
Layout
├─ Sidebar
│  ├─ Logo
│  ├─ Navigation Links
│  │  ├─ Home
│  │  ├─ History
│  │  └─ Settings
│  └─ Version Info
└─ Main Content Area
   └─ {children} (routed pages)
```

### JobStatusPage (Main Feature Page)

```
JobStatusPage
├─ Header
│  ├─ Job ID
│  ├─ Status Badge
│  ├─ Progress Bar
│  └─ Timestamps
├─ Error Message (if failed)
├─ Download Button (if completed)
├─ Tab Navigation (8 tabs)
└─ Tab Content (dynamic based on activeTab)
   ├─ Pipeline Tab → PipelineVisualization
   ├─ Stats Tab → StatsDashboard
   ├─ Components Tab → ComponentVisualization
   ├─ Tech Mapping Tab → TechnologyMapping
   ├─ Business Rules Tab → BusinessRulesTracker
   ├─ Code Preview Tab → CodePreview
   ├─ Artifacts Tab → ArtifactViewer
   └─ Logs Tab → LogsViewer
```

---

## State Management

### Global State (React Context)

```javascript
ApiContext
├─ apiUrl: string (default: "http://localhost:8000")
├─ updateApiUrl: (url: string) => void
└─ Persisted in localStorage
```

### Local State (Component Level)

```javascript
JobStatusPage
├─ job: MigrationJob | null
├─ loading: boolean
├─ error: string
├─ activeTab: string
└─ Polling interval (useEffect)

HomePage
├─ selectedMethod: 'github' | 'folder' | 'upload'
└─ Form-specific state in child components

HistoryPage
└─ jobs: MigrationJob[] (from localStorage)

SettingsPage
├─ url: string
└─ saved: boolean
```

---

## API Integration

### Endpoints Used

```typescript
// Create migration from GitHub
POST /api/v1/migrate/github
Body: { github_url: string, branch?: string }
Response: { job_id: string, status: string, message: string }

// Create migration from upload
POST /api/v1/migrate/upload
Body: FormData with 'file' field
Response: { job_id: string, status: string, message: string }

// Get job status
GET /api/v1/migrate/{job_id}/status
Response: {
  job_id: string,
  status: string,
  current_step: string,
  progress_pct: number,
  error_message?: string,
  created_at: datetime,
  completed_at?: datetime,
  logs: string[],
  discovered_technologies: string[],
  business_rules: string[],
  generated_files: string[],
  metadata: {
    technology_inventory: {...},
    component_inventory: {...},
    docs_research: {...},
    migration_plan: {...},
    ...
  }
}

// Download result
GET /api/v1/migrate/{job_id}/result
Response: ZIP file (application/zip)
```

---

## Electron IPC Communication

### Main Process → Renderer

```javascript
// Preload script exposes:
window.electronAPI = {
  selectFolder: () => Promise<{canceled, folderPath}>,
  zipFolder: (path) => Promise<{success, zipPath, size}>,
  selectFile: () => Promise<{canceled, filePath}>,
  saveFile: (name) => Promise<{canceled, filePath}>,
  onZipProgress: (callback) => void
}
```

### Usage in Components

```javascript
// LocalFolderForm.jsx
const result = await window.electronAPI.selectFolder();
if (!result.canceled) {
  setSelectedFolder(result.folderPath);
  const zipResult = await window.electronAPI.zipFolder(result.folderPath);
  // Upload zipResult.zipPath to backend
}
```

---

## Technology Stack

### Frontend
- **React 18**: UI framework
- **React Router 6**: Client-side routing
- **TailwindCSS 3**: Utility-first CSS
- **Lucide React**: Icon library
- **Axios**: HTTP client
- **Vite 5**: Build tool & dev server

### Desktop
- **Electron 29**: Desktop framework
- **Archiver**: ZIP file creation
- **Concurrently**: Run multiple commands
- **Wait-on**: Wait for dev server

### Build & Dev
- **electron-builder**: Package for distribution
- **PostCSS**: CSS processing
- **Autoprefixer**: CSS vendor prefixes

---

## File Organization

```
Separation of Concerns:
├─ electron/        → Native desktop features
├─ src/components/  → Reusable UI components
├─ src/pages/       → Route-level components
├─ src/context/     → Global state management
└─ src/             → App entry & global styles

Component Naming:
- PascalCase for components
- camelCase for functions/variables
- kebab-case for file names (optional)

Import Order:
1. React & React libraries
2. Third-party libraries
3. Local components
4. Context & utilities
5. Assets & styles
```

---

## Performance Considerations

### Optimizations Implemented
- Polling stops when job completes
- Debounced search inputs (300ms)
- Lazy rendering for large lists
- Efficient re-renders (React.memo candidates)
- Code splitting ready (dynamic imports)

### Future Optimizations
- Virtual scrolling for large logs
- Memoized expensive computations
- Web Workers for heavy processing
- IndexedDB for large datasets

---

## Security Considerations

### Current Implementation
- CORS enabled on backend
- No sensitive data in localStorage
- API URL configurable (not hardcoded)
- File uploads validated on backend

### Future Enhancements
- API key authentication
- Encrypted local storage
- Content Security Policy (CSP)
- Sandboxed renderer process

---

## Build & Distribution

### Development Build
```bash
npm run electron:dev
→ Vite dev server (hot reload)
→ Electron in development mode
→ DevTools enabled
```

### Production Build
```bash
npm run electron:build
→ Vite production build (minified)
→ Electron packaged with electron-builder
→ Platform-specific installers
```

### Output
- **Windows**: `release/Spring2Fast Setup 0.1.0.exe`
- **macOS**: `release/Spring2Fast-0.1.0.dmg`
- **Linux**: `release/Spring2Fast-0.1.0.AppImage`

---

**This architecture provides a solid foundation for a scalable, maintainable desktop application!** 🏗️
