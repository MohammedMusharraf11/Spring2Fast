import { useState } from 'react';
import { CheckCircle2, AlertTriangle, Circle, Search } from 'lucide-react';

const BusinessRulesTracker = ({ businessRules = [] }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filter, setFilter] = useState('all');

  // Parse rules to extract class and method info
  const parseRule = (rule) => {
    const match = rule.match(/^([^.]+)\.([^:]+):\s*(.+)$/);
    if (match) {
      return {
        className: match[1],
        methodName: match[2],
        description: match[3],
        original: rule
      };
    }
    return {
      className: 'General',
      methodName: '',
      description: rule,
      original: rule
    };
  };

  const parsedRules = businessRules.map((rule) => ({
    ...parseRule(rule),
    // Simulate verification status (in real app, this would come from backend)
    status: Math.random() > 0.3 ? 'verified' : Math.random() > 0.5 ? 'warning' : 'pending'
  }));

  const filteredRules = parsedRules.filter((rule) => {
    if (filter !== 'all' && rule.status !== filter) return false;
    if (searchTerm && !rule.original.toLowerCase().includes(searchTerm.toLowerCase())) {
      return false;
    }
    return true;
  });

  const getStatusIcon = (status) => {
    switch (status) {
      case 'verified':
        return <CheckCircle2 className="w-5 h-5 text-green-600" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-yellow-600" />;
      default:
        return <Circle className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'verified':
        return 'bg-green-50 border-green-200';
      case 'warning':
        return 'bg-yellow-50 border-yellow-200';
      default:
        return 'bg-gray-50 border-gray-200';
    }
  };

  const statusCounts = {
    all: parsedRules.length,
    verified: parsedRules.filter((r) => r.status === 'verified').length,
    warning: parsedRules.filter((r) => r.status === 'warning').length,
    pending: parsedRules.filter((r) => r.status === 'pending').length
  };

  return (
    <div className="space-y-4">
      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-2xl font-bold text-gray-900">{statusCounts.all}</div>
          <div className="text-sm text-gray-600">Total Rules</div>
        </div>
        <div className="bg-green-50 rounded-lg border border-green-200 p-4">
          <div className="text-2xl font-bold text-green-700">{statusCounts.verified}</div>
          <div className="text-sm text-green-600">Verified</div>
        </div>
        <div className="bg-yellow-50 rounded-lg border border-yellow-200 p-4">
          <div className="text-2xl font-bold text-yellow-700">{statusCounts.warning}</div>
          <div className="text-sm text-yellow-600">Needs Review</div>
        </div>
        <div className="bg-gray-50 rounded-lg border border-gray-200 p-4">
          <div className="text-2xl font-bold text-gray-700">{statusCounts.pending}</div>
          <div className="text-sm text-gray-600">Pending</div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex items-center gap-3">
          <div className="flex gap-2">
            <button
              onClick={() => setFilter('all')}
              className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                filter === 'all'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setFilter('verified')}
              className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                filter === 'verified'
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Verified
            </button>
            <button
              onClick={() => setFilter('warning')}
              className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                filter === 'warning'
                  ? 'bg-yellow-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Needs Review
            </button>
            <button
              onClick={() => setFilter('pending')}
              className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                filter === 'pending'
                  ? 'bg-gray-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Pending
            </button>
          </div>
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search rules..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>
      </div>

      {/* Rules List */}
      <div className="space-y-2">
        {filteredRules.length > 0 ? (
          filteredRules.map((rule, index) => (
            <div
              key={index}
              className={`flex items-start gap-3 p-4 rounded-lg border ${getStatusColor(
                rule.status
              )}`}
            >
              {getStatusIcon(rule.status)}
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-semibold text-gray-900">{rule.className}</span>
                  {rule.methodName && (
                    <>
                      <span className="text-gray-400">•</span>
                      <span className="text-gray-700">{rule.methodName}</span>
                    </>
                  )}
                </div>
                <div className="text-sm text-gray-700">{rule.description}</div>
              </div>
            </div>
          ))
        ) : (
          <div className="text-center py-12 text-gray-500">
            {businessRules.length === 0
              ? 'No business rules extracted yet'
              : 'No rules match your filter'}
          </div>
        )}
      </div>
    </div>
  );
};

export default BusinessRulesTracker;
