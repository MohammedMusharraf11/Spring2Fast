import { useState } from 'react';
import { FileCode, Folder, ChevronRight, ChevronDown, Eye, Copy } from 'lucide-react';

const CodePreview = ({ generatedFiles = [] }) => {
  const [expandedFolders, setExpandedFolders] = useState({ app: true });
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState('');

  // Build file tree structure
  const buildFileTree = () => {
    const tree = {};
    generatedFiles.forEach((file) => {
      const parts = file.split('/');
      let current = tree;
      parts.forEach((part, index) => {
        if (index === parts.length - 1) {
          if (!current._files) current._files = [];
          current._files.push(part);
        } else {
          if (!current[part]) current[part] = {};
          current = current[part];
        }
      });
    });
    return tree;
  };

  const fileTree = buildFileTree();

  const toggleFolder = (path) => {
    setExpandedFolders((prev) => ({
      ...prev,
      [path]: !prev[path]
    }));
  };

  const handleFileClick = (filePath) => {
    setSelectedFile(filePath);
    // In real implementation, fetch file content from backend
    setFileContent(`# ${filePath}\n\n# This is a preview of the generated file\n# Full content will be available after download\n\nfrom fastapi import APIRouter\n\nrouter = APIRouter()\n\n@router.get("/")\nasync def example():\n    return {"message": "Generated endpoint"}`);
  };

  const renderTree = (node, path = '', level = 0) => {
    return (
      <div>
        {Object.entries(node).map(([key, value]) => {
          if (key === '_files') {
            return value.map((file) => {
              const fullPath = path ? `${path}/${file}` : file;
              return (
                <button
                  key={fullPath}
                  onClick={() => handleFileClick(fullPath)}
                  className={`flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-gray-100 rounded transition-colors ${
                    selectedFile === fullPath ? 'bg-blue-50 text-blue-700' : 'text-gray-700'
                  }`}
                  style={{ paddingLeft: `${(level + 1) * 12 + 12}px` }}
                >
                  <FileCode className="w-4 h-4" />
                  {file}
                </button>
              );
            });
          }

          const folderPath = path ? `${path}/${key}` : key;
          const isExpanded = expandedFolders[folderPath];

          return (
            <div key={folderPath}>
              <button
                onClick={() => toggleFolder(folderPath)}
                className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-gray-100 rounded transition-colors text-gray-700"
                style={{ paddingLeft: `${level * 12 + 12}px` }}
              >
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4" />
                ) : (
                  <ChevronRight className="w-4 h-4" />
                )}
                <Folder className="w-4 h-4 text-blue-500" />
                {key}
              </button>
              {isExpanded && renderTree(value, folderPath, level + 1)}
            </div>
          );
        })}
      </div>
    );
  };

  const copyCode = () => {
    navigator.clipboard.writeText(fileContent);
  };

  return (
    <div className="grid grid-cols-3 gap-6 h-[600px]">
      {/* File Tree */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="bg-gray-50 border-b border-gray-200 px-4 py-3">
          <h3 className="font-semibold text-gray-900 text-sm">File Explorer</h3>
        </div>
        <div className="overflow-y-auto h-[calc(100%-48px)] p-2">
          {generatedFiles.length > 0 ? (
            renderTree(fileTree)
          ) : (
            <div className="text-center py-12 text-gray-500 text-sm">
              No files generated yet
            </div>
          )}
        </div>
      </div>

      {/* Code Viewer */}
      <div className="col-span-2 bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="bg-gray-50 border-b border-gray-200 px-4 py-3 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900 text-sm">
            {selectedFile || 'Select a file to preview'}
          </h3>
          {selectedFile && (
            <button
              onClick={copyCode}
              className="px-3 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors flex items-center gap-2 text-sm"
            >
              <Copy className="w-4 h-4" />
              Copy
            </button>
          )}
        </div>
        <div className="overflow-y-auto h-[calc(100%-48px)] p-4">
          {selectedFile ? (
            <pre className="text-sm font-mono text-gray-800 whitespace-pre-wrap">
              {fileContent}
            </pre>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-500">
              <Eye className="w-12 h-12 mb-3 text-gray-300" />
              <p className="text-sm">Select a file from the tree to preview</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CodePreview;
