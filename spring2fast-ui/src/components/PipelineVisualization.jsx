import {
  CheckCircle2, Loader2, Clock, AlertCircle, Database, Package, Briefcase,
  Frame, Search, Lightbulb, Pickaxe, TestTube2, Combine, Workflow, GitMerge
} from 'lucide-react';

/*
 * DAG node layout:
 *
 *                            ingest
 *                         ╱    │    ╲
 *             tech_discover  biz_logic  discover_components
 *                         ╲    │    ╱
 *                        merge_analysis
 *                             │
 *                        research_docs
 *                             │
 *                           analyze
 *                             │
 *                            plan
 *                             │
 *                       ┌─ migrate ──┐
 *                       │ (subgraph) │
 *                       └────────────┘
 *                             │
 *                          validate ──→ (retry migrate)
 *                             │
 *                          assemble
 */

const NODES = {
  ingest:              { label: 'Ingest Source',         progress: 10,  icon: Database },
  tech_discover:       { label: 'Tech Discovery',       progress: 20,  icon: Search },
  extract_business:    { label: 'Business Logic',       progress: 20,  icon: Briefcase },
  discover_components: { label: 'Component Discovery',  progress: 20,  icon: Frame },
  merge_analysis:      { label: 'Merge Analysis',       progress: 30,  icon: GitMerge },
  research_docs:       { label: 'Docs Research',         progress: 40,  icon: Lightbulb },
  analyze:             { label: 'Analysis',              progress: 50,  icon: Package },
  plan:                { label: 'Migration Planning',    progress: 55,  icon: Workflow },
  migrate:             { label: 'Code Generation',       progress: 80,  icon: Pickaxe, isSubgraph: true },
  validate:            { label: 'Validation',            progress: 90,  icon: TestTube2 },
  assemble:            { label: 'Assembly & Packaging',  progress: 100, icon: Combine },
};

const getNodeStatus = (nodeKey, jobStatus, jobProgress) => {
  if (jobStatus === 'completed') return 'completed';
  if (jobStatus === 'failed') {
    // Mark the node where failure happened
    const node = NODES[nodeKey];
    const nodeProgress = node?.progress || 0;
    if (jobProgress < nodeProgress) return 'pending';
    if (jobProgress >= nodeProgress) {
      // Check if this is the failing node (progress is within this node's range)
      const nextProgress = Object.values(NODES)
        .map(n => n.progress)
        .filter(p => p > nodeProgress)
        .sort((a, b) => a - b)[0] || 100;
      if (jobProgress < nextProgress) return 'failed';
      return 'completed';
    }
  }

  const node = NODES[nodeKey];
  if (!node) return 'pending';

  if (jobProgress >= node.progress) return 'completed';

  // Find the active node
  const sortedNodes = Object.entries(NODES).sort((a, b) => a[1].progress - b[1].progress);
  const activeNode = sortedNodes.find(([, n]) => jobProgress < n.progress);
  if (activeNode && activeNode[0] === nodeKey) return 'active';

  // For parallel nodes, check if any sibling is active
  const parallelNodes = ['tech_discover', 'extract_business', 'discover_components'];
  if (parallelNodes.includes(nodeKey) && jobProgress >= 10 && jobProgress < 30) return 'active';

  return 'pending';
};

const NodeBox = ({ nodeKey, status, isSubgraph = false }) => {
  const node = NODES[nodeKey];
  if (!node) return null;

  const Icon = node.icon;
  const isCompleted = status === 'completed';
  const isActive = status === 'active';
  const isFailed = status === 'failed';
  const isPending = status === 'pending';

  let borderColor = 'var(--border-subtle)';
  let bgColor = 'var(--surface-1)';
  let iconColor = 'var(--text-muted)';

  if (isCompleted) {
    borderColor = 'hsla(155, 65%, 45%, 0.4)';
    bgColor = 'hsla(155, 65%, 45%, 0.05)';
    iconColor = 'hsl(155, 65%, 55%)';
  } else if (isActive) {
    borderColor = 'hsla(225, 80%, 60%, 0.6)';
    bgColor = 'hsla(225, 80%, 60%, 0.1)';
    iconColor = 'hsl(225, 80%, 65%)';
  } else if (isFailed) {
    borderColor = 'hsla(0, 70%, 55%, 0.5)';
    bgColor = 'hsla(0, 70%, 55%, 0.1)';
    iconColor = 'hsl(0, 65%, 65%)';
  }

  return (
    <div
      className={`card-interactive animate-fade-in ${isActive ? 'animate-pulse-glow' : ''}`}
      style={{
        padding: '14px 18px',
        border: `1px solid ${borderColor}`,
        borderStyle: isSubgraph ? 'dashed' : 'solid',
        background: bgColor,
        borderRadius: isSubgraph ? 20 : 14,
        display: 'flex', alignItems: 'center', gap: 14,
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        opacity: isPending ? 0.55 : 1,
        flex: 1,
        minWidth: 0,
      }}
    >
      <div style={{
        width: 38, height: 38, borderRadius: 10, background: 'var(--surface-0)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        border: `1px solid ${borderColor}`, color: iconColor, flexShrink: 0
      }}>
        <Icon size={18} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <h3 style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {node.label}
        </h3>
        <p className="font-mono" style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
          {nodeKey}
        </p>
      </div>
      <div style={{ flexShrink: 0 }}>
        {isCompleted && <span className="badge badge-green"><CheckCircle2 size={11} /> Done</span>}
        {isActive && <span className="badge badge-blue"><Loader2 size={11} className="animate-spin-slow" /> Running</span>}
        {isFailed && <span className="badge badge-red"><AlertCircle size={11} /> Failed</span>}
      </div>
    </div>
  );
};

const Connector = ({ completed, active, height = 24 }) => (
  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', height, position: 'relative' }}>
    <div style={{
      width: 2, height: '100%',
      background: completed ? 'hsl(155, 65%, 45%)' : active ? 'hsl(225, 80%, 60%)' : 'var(--surface-3)',
      position: 'relative', overflow: 'hidden'
    }}>
      {active && (
        <div style={{
          position: 'absolute', top: '-100%', left: 0, right: 0, height: '200%',
          background: 'repeating-linear-gradient(180deg, transparent, transparent 4px, hsl(225, 80%, 60%) 4px, hsl(225, 80%, 60%) 8px)',
          animation: 'shimmer 1s linear infinite'
        }} />
      )}
    </div>
    <div style={{
      position: 'absolute', bottom: -2, width: 0, height: 0,
      borderLeft: '4px solid transparent', borderRight: '4px solid transparent',
      borderTop: `5px solid ${completed ? 'hsl(155, 65%, 45%)' : active ? 'hsl(225, 80%, 60%)' : 'var(--surface-3)'}`
    }} />
  </div>
);

const PipelineVisualization = ({ state }) => {
  const jobStatus = state?.status || 'pending';
  const jobProgress = state?.progress_pct || 0;

  const s = (key) => getNodeStatus(key, jobStatus, jobProgress);
  const parallelDone = s('tech_discover') === 'completed';
  const parallelActive = s('tech_discover') === 'active';

  return (
    <div className="card" style={{ padding: '28px 24px', overflow: 'hidden' }}>
      <div style={{ marginBottom: 20, paddingBottom: 14, borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Workflow size={20} style={{ color: 'hsl(225, 80%, 65%)' }} />
        <h2 style={{ fontSize: '1.05rem', fontWeight: 600 }}>Agentic DAG Workflow</h2>
      </div>

      <div style={{ maxWidth: 640, margin: '0 auto', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        {/* Start */}
        <div style={{
          padding: '5px 14px', borderRadius: 99, background: 'var(--surface-2)',
          border: '1px dashed var(--border-default)', fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-secondary)'
        }}>__start__</div>
        <Connector completed={s('ingest') === 'completed'} active={s('ingest') === 'active'} />

        {/* Ingest */}
        <div style={{ width: '100%' }}><NodeBox nodeKey="ingest" status={s('ingest')} /></div>

        {/* Fan-out indicator */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', position: 'relative', height: 28 }}>
          <div style={{
            position: 'absolute', top: 0, left: '50%', transform: 'translateX(-50%)',
            width: 2, height: 28, background: parallelDone ? 'hsl(155, 65%, 45%)' : parallelActive ? 'hsl(225, 80%, 60%)' : 'var(--surface-3)',
          }} />
          {/* Horizontal spread lines */}
          <div style={{
            position: 'absolute', bottom: 0, width: '80%', height: 2,
            background: parallelDone ? 'hsl(155, 65%, 45%)' : parallelActive ? 'hsl(225, 80%, 60%)' : 'var(--surface-3)',
          }} />
        </div>

        {/* Parallel branches */}
        <div style={{ display: 'flex', gap: 10, width: '100%' }}>
          <NodeBox nodeKey="tech_discover" status={s('tech_discover')} />
          <NodeBox nodeKey="extract_business" status={s('extract_business')} />
          <NodeBox nodeKey="discover_components" status={s('discover_components')} />
        </div>

        {/* Fan-in indicator */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', position: 'relative', height: 28 }}>
          <div style={{
            position: 'absolute', top: 0, width: '80%', height: 2,
            background: parallelDone ? 'hsl(155, 65%, 45%)' : 'var(--surface-3)',
          }} />
          <div style={{
            position: 'absolute', top: 0, left: '50%', transform: 'translateX(-50%)',
            width: 2, height: 28, background: parallelDone ? 'hsl(155, 65%, 45%)' : 'var(--surface-3)',
          }} />
        </div>

        {/* Sequential: merge → research → analyze → plan */}
        {['merge_analysis', 'research_docs', 'analyze', 'plan'].map((key) => (
          <div key={key} style={{ width: '100%' }}>
            <NodeBox nodeKey={key} status={s(key)} />
            <Connector completed={s(key) === 'completed'} active={s(key) === 'active'} />
          </div>
        ))}

        {/* Migrate subgraph */}
        <div style={{ width: '100%' }}><NodeBox nodeKey="migrate" status={s('migrate')} isSubgraph /></div>
        <Connector completed={s('migrate') === 'completed'} active={s('migrate') === 'active'} />

        {/* Validate (with retry arrow) */}
        <div style={{ width: '100%', position: 'relative' }}>
          <NodeBox nodeKey="validate" status={s('validate')} />
          {/* Retry loop indicator */}
          <div style={{
            position: 'absolute', right: -8, top: '50%', transform: 'translateY(-50%)',
            fontSize: '0.65rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4,
            padding: '2px 8px', borderRadius: 8, background: 'var(--surface-2)', border: '1px dashed var(--border-subtle)',
            whiteSpace: 'nowrap',
          }}>
            ↺ retry
          </div>
        </div>
        <Connector completed={s('validate') === 'completed'} active={s('validate') === 'active'} />

        {/* Assemble */}
        <div style={{ width: '100%' }}><NodeBox nodeKey="assemble" status={s('assemble')} /></div>

        {/* End */}
        <Connector completed={jobStatus === 'completed'} />
        <div style={{
          padding: '5px 14px', borderRadius: 99, background: 'var(--surface-2)',
          border: '1px dashed var(--border-default)', fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-secondary)'
        }}>__end__</div>
      </div>
    </div>
  );
};

export default PipelineVisualization;
