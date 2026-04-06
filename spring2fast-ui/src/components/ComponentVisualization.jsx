import { useState } from 'react';
import { ChevronDown, ChevronRight, Box, Database, Layers, FileCode, Shield } from 'lucide-react';

const ComponentVisualization = ({ componentInventory = {} }) => {
  const [expandedCategories, setExpandedCategories] = useState({
    controllers: true,
    services: false,
    repositories: false,
    entities: false,
    dtos: false
  });

  const [selectedComponent, setSelectedComponent] = useState(null);

  const categoryConfig = {
    controllers: { icon: Layers, color: 'blue', label: 'Controllers' },
    services: { icon: Box, color: 'green', label: 'Services' },
    repositories: { icon: Database, color: 'purple', label: 'Repositories' },
    entities: { icon: FileCode, color: 'yellow', label: 'Entities' },
    dtos: { icon: FileCode, color: 'pink', label: 'DTOs' },
    security: { icon: Shield, color: 'red', label: 'Security' }
  };

  const toggleCategory = (category) => {
    setExpandedCategories((prev) => ({
      ...prev,
      [category]: !prev[category]
    }));
  };

  const renderComponent = (component, category) => {
    const config = categoryConfig[category];
    const Icon = config.icon;
    const methods = component.methods || [];
    const fields = component.fields || [];
    const mappings = component.request_mappings || [];

    return (
      <div
        key={component.class_name}
        className="ml-6 mb-3 border-l-2 border-gray-200 pl-4"
      >
        <button
          onClick={() => setSelectedComponent(component)}
          className="flex items-center gap-2 text-left hover:bg-gray-50 p-2 rounded-lg w-full transition-colors"
        >
          <Icon className={`w-4 h-4 text-${config.color}-600`} />
          <span className="font-medium text-gray-900">{component.class_name}</span>
          <span className="text-xs text-gray-500">
            ({methods.length} methods)
          </span>
        </button>

        {selectedComponent?.class_name === component.class_name && (
          <div className="mt-2 ml-6 space-y-2">
            {mappings.length > 0 && (
              <div className="bg-blue-50 rounded-lg p-3">
                <div className="text-xs font-semibold text-blue-900 mb-2">Endpoints</div>
                {mappings.slice(0, 5).map((mapping, idx) => (
                  <div key={idx} className="text-xs text-blue-700 font-mono">
                    {mapping}
                  </div>
                ))}
              </div>
            )}

            {methods.length > 0 && (
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="text-xs font-semibold text-gray-900 mb-2">Methods</div>
                <div className="space-y-1">
                  {methods.slice(0, 8).map((method, idx) => (
                    <div key={idx} className="text-xs text-gray-700 font-mono">
                      • {method}
                    </div>
                  ))}
                  {methods.length > 8 && (
                    <div className="text-xs text-gray-500">
                      +{methods.length - 8} more...
                    </div>
                  )}
                </div>
              </div>
            )}

            {fields.length > 0 && (
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="text-xs font-semibold text-gray-900 mb-2">Fields</div>
                <div className="space-y-1">
                  {fields.slice(0, 8).map((field, idx) => (
                    <div key={idx} className="text-xs text-gray-700 font-mono">
                      • {field.name}: {field.type}
                    </div>
                  ))}
                  {fields.length > 8 && (
                    <div className="text-xs text-gray-500">
                      +{fields.length - 8} more...
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {Object.entries(componentInventory).map(([category, components]) => {
        if (!Array.isArray(components) || components.length === 0) return null;

        const config = categoryConfig[category];
        if (!config) return null;

        const Icon = config.icon;
        const isExpanded = expandedCategories[category];

        return (
          <div key={category} className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <button
              onClick={() => toggleCategory(category)}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <Icon className={`w-5 h-5 text-${config.color}-600`} />
                <span className="font-semibold text-gray-900">{config.label}</span>
                <span className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded-full">
                  {components.length}
                </span>
              </div>
              {isExpanded ? (
                <ChevronDown className="w-5 h-5 text-gray-400" />
              ) : (
                <ChevronRight className="w-5 h-5 text-gray-400" />
              )}
            </button>

            {isExpanded && (
              <div className="p-4 pt-0 border-t border-gray-100">
                {components.map((component) => renderComponent(component, category))}
              </div>
            )}
          </div>
        );
      })}

      {Object.keys(componentInventory).length === 0 && (
        <div className="text-center py-12 text-gray-500">
          No components discovered yet
        </div>
      )}
    </div>
  );
};

export default ComponentVisualization;
