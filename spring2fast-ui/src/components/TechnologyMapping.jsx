import { ArrowRight, ExternalLink, Copy, CheckCircle2 } from 'lucide-react';
import { useState } from 'react';

const TechnologyMapping = ({ technologies = [], docsReferences = [] }) => {
  const [copiedCommand, setCopiedCommand] = useState(false);

  const mappings = {
    'spring-boot': { python: 'fastapi', pip: 'fastapi uvicorn[standard]' },
    'spring-web': { python: 'fastapi', pip: 'fastapi' },
    'spring-data-jpa': { python: 'sqlalchemy', pip: 'sqlalchemy' },
    'hibernate': { python: 'sqlalchemy', pip: 'sqlalchemy' },
    'spring-security': { python: 'fastapi-security', pip: 'python-jose[cryptography] passlib[bcrypt]' },
    'postgresql': { python: 'psycopg2', pip: 'psycopg2-binary' },
    'mysql': { python: 'pymysql', pip: 'pymysql' },
    'mongodb': { python: 'pymongo', pip: 'pymongo' },
    'redis': { python: 'redis-py', pip: 'redis' },
    'kafka': { python: 'aiokafka', pip: 'aiokafka' },
    'rabbitmq': { python: 'pika', pip: 'pika' },
    'supabase': { python: 'supabase-py', pip: 'supabase' },
    'jwt': { python: 'pyjwt', pip: 'pyjwt' },
    'lombok': { python: 'pydantic', pip: 'pydantic' },
    'docker': { python: 'docker', pip: 'docker' }
  };

  const allPipPackages = technologies
    .map((tech) => mappings[tech]?.pip)
    .filter(Boolean)
    .join(' ');

  const copyPipCommand = () => {
    navigator.clipboard.writeText(`pip install ${allPipPackages}`);
    setCopiedCommand(true);
    setTimeout(() => setCopiedCommand(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Quick Install */}
      {allPipPackages && (
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-200 p-6">
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-blue-600" />
            Quick Install Command
          </h3>
          <div className="flex items-center gap-3">
            <code className="flex-1 bg-white px-4 py-3 rounded-lg text-sm font-mono text-gray-800 border border-blue-200">
              pip install {allPipPackages}
            </code>
            <button
              onClick={copyPipCommand}
              className="px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
            >
              {copiedCommand ? (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  Copy
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Mapping Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">
                  Java Technology
                </th>
                <th className="px-6 py-3 text-center text-xs font-semibold text-gray-700 uppercase">
                  
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">
                  Python Equivalent
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase">
                  Pip Package
                </th>
                <th className="px-6 py-3 text-center text-xs font-semibold text-gray-700 uppercase">
                  Docs
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {technologies.map((tech) => {
                const mapping = mappings[tech];
                const docRef = docsReferences.find((ref) => ref.java_technology === tech);

                return (
                  <tr key={tech} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-orange-500 rounded-full" />
                        <span className="font-medium text-gray-900">{tech}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <ArrowRight className="w-5 h-5 text-gray-400 mx-auto" />
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-blue-500 rounded-full" />
                        <span className="font-medium text-gray-900">
                          {mapping?.python || docRef?.python_equivalent || 'N/A'}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <code className="text-sm bg-gray-100 px-2 py-1 rounded text-gray-800">
                        {mapping?.pip || 'N/A'}
                      </code>
                    </td>
                    <td className="px-6 py-4 text-center">
                      {docRef?.official_docs && (
                        <a
                          href={docRef.official_docs}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-700"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {technologies.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          No technologies detected yet
        </div>
      )}
    </div>
  );
};

export default TechnologyMapping;
