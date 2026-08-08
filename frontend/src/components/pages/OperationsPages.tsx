import { ReactNode, useMemo, useState } from "react";

import { EvaluationRun, SystemHealth, Task } from "../../api";
import { useTranslation } from "../../i18n/LocaleProvider";
import { PageHeader } from "../workspace/PageHeader";
import { WorkspacePanel } from "../workspace/WorkspacePanel";

type RunsPageProps = {
  inspector: ReactNode;
  launcher: ReactNode;
  onSelect: (runId: string) => void;
  preflight: ReactNode;
  renderActions: (run: EvaluationRun) => ReactNode;
  runs: EvaluationRun[];
  selectedRunId: string | null;
};

export function RunInventory({ onSelect, renderActions, runs, selectedRunId }: Omit<RunsPageProps, "inspector" | "launcher" | "preflight">) {
  const { formatDate } = useTranslation();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const statuses = useMemo(() => Array.from(new Set(runs.map((run) => run.status))).sort(), [runs]);
  const visibleRuns = useMemo(() => runs.filter((run) => {
    const searchable = `${run.benchmark_id} ${run.benchmark_version} ${run.status} ${run.id}`.toLowerCase();
    return (status === "all" || run.status === status) && searchable.includes(query.trim().toLowerCase());
  }), [query, runs, status]);

  return <WorkspacePanel className="workspace-run-inventory" description="Select a snapshot to inspect lifecycle evidence and exportable artifacts." title="Run inventory" toolbar={<span className="workspace-count">{visibleRuns.length}/{runs.length} runs</span>}>
    <div className="workspace-operation-toolbar">
      <label className="workspace-filter-control">Find run<input aria-label="Find run" onChange={(event) => setQuery(event.target.value)} placeholder="Benchmark, status, or ID" value={query} /></label>
      <label className="workspace-filter-control">Run status<select aria-label="Run status" onChange={(event) => setStatus(event.target.value)} value={status}><option value="all">All states</option>{statuses.map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}</select></label>
    </div>
    {runs.length === 0 ? <p className="empty">Verify a model endpoint to create the first run.</p> : visibleRuns.length === 0 ? <p className="empty">No runs match the current filters.</p> : <div className="workspace-run-list">{visibleRuns.map((run) => <article className={selectedRunId === run.id ? "workspace-run-row is-selected" : "workspace-run-row"} key={run.id}>
      <button aria-pressed={selectedRunId === run.id} className="workspace-run-summary" onClick={() => onSelect(run.id)} type="button"><strong data-i18n-preserve>{run.benchmark_id} v{run.benchmark_version}</strong><span><span className={`badge ${run.status}`}>{run.status.replaceAll("_", " ")}</span>{run.completed_samples}/{run.total_samples} samples · {formatDate(run.created_at)}</span></button>
      <div className="workspace-run-actions">{renderActions(run)}</div>
    </article>)}</div>}
  </WorkspacePanel>;
}

export function RunsPage({ inspector, launcher, onSelect, preflight, renderActions, runs, selectedRunId }: RunsPageProps) {
  const selectedVisible = runs.some((run) => run.id === selectedRunId);
  return <div className="workspace-page runs-page">
    <PageHeader description="Launch immutable evaluation snapshots, then inspect their operational and evidence trail." eyebrow="Operations" status={<>{runs.length} total runs</>} title="Runs" />
    <div className="workspace-run-launch-grid">
      <WorkspacePanel description="Validate endpoint compatibility and capacity before a queue entry is created." title="Run preflight">{preflight}</WorkspacePanel>
      <WorkspacePanel description="Choose an available dataset, prompt version, and endpoint for a new evaluation." title="Queue dataset evaluation">{launcher}</WorkspacePanel>
    </div>
    <div className="workspace-split workspace-split--runs">
      <RunInventory onSelect={onSelect} renderActions={renderActions} runs={runs} selectedRunId={selectedRunId} />
      {selectedVisible ? <section className="workspace-run-detail" aria-label="Selected run inspector">{inspector}</section> : <WorkspacePanel className="workspace-run-detail-empty" description="Select a run from the persistent inventory to open its summary, evidence, and lifecycle history." title="Select a run" />}
    </div>
  </div>;
}

type QueuePageProps = {
  busy: string | null;
  onPriority: (task: Task, priority: number) => Promise<void>;
  tasks: Task[];
};

export function editableTaskPriority(task: Task) {
  return ["pending", "retry_scheduled"].includes(task.status);
}

export function QueuePage({ busy, onPriority, tasks }: QueuePageProps) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const statuses = useMemo(() => Array.from(new Set(tasks.map((task) => task.status))).sort(), [tasks]);
  const visibleTasks = useMemo(() => tasks.filter((task) => {
    const searchable = `${task.task_type} ${task.status} ${task.run_id} ${task.leased_by ?? ""}`.toLowerCase();
    return (status === "all" || task.status === status) && searchable.includes(query.trim().toLowerCase());
  }), [query, status, tasks]);

  return <div className="workspace-page queue-page">
    <PageHeader description="Monitor queued work, prioritise eligible tasks, and trace each task back to its immutable run." eyebrow="Operations" status={<>{visibleTasks.length}/{tasks.length} tasks visible</>} title="Task queue" />
    <WorkspacePanel description="Virtualised rows keep high-volume queues responsive while retaining task-level operational controls." title="Queue inventory" toolbar={<span className="workspace-count">{tasks.filter((task) => ["leased", "running"].includes(task.status)).length} active</span>}>
      <div className="workspace-operation-toolbar">
        <label className="workspace-filter-control">Find task<input aria-label="Find task" onChange={(event) => setQuery(event.target.value)} placeholder="Type, run, worker, or ID" value={query} /></label>
        <label className="workspace-filter-control">Task status<select aria-label="Task status" onChange={(event) => setStatus(event.target.value)} value={status}><option value="all">All states</option>{statuses.map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}</select></label>
      </div>
      {tasks.length === 0 ? <p className="empty">No queued work exists.</p> : visibleTasks.length === 0 ? <p className="empty">No tasks match the current filters.</p> : <VirtualTaskQueue busy={busy} onPriority={onPriority} tasks={visibleTasks} />}
    </WorkspacePanel>
  </div>;
}

export function VirtualTaskQueue({ busy, onPriority, tasks }: QueuePageProps) {
  const { formatDate } = useTranslation();
  const rowHeight = 52;
  const windowSize = 30;
  const [scrollTop, setScrollTop] = useState(0);
  const start = Math.max(0, Math.floor(scrollTop / rowHeight) - 4);
  const end = Math.min(tasks.length, start + windowSize + 8);
  const visible = tasks.slice(start, end);
  return <div className="table-wrap virtual-table-viewport workspace-queue-table" onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}><table><thead><tr><th>Task</th><th>Parent</th><th>Run</th><th>Status</th><th>Priority</th><th>Attempts</th><th>Worker</th><th>Created</th></tr></thead><tbody>{start > 0 && <tr aria-hidden="true"><td colSpan={8} className="virtual-spacer" style={{ height: start * rowHeight }} /></tr>}{visible.map((task) => <tr key={task.id}><td>{task.task_type}</td><td>{task.parent_task_id?.slice(0, 8) ?? "--"}</td><td>{task.run_id.slice(0, 8)}</td><td><span className={`badge ${task.status}`}>{task.status.replaceAll("_", " ")}</span></td><td><div className="actions"><span>{task.priority}</span><button aria-label={`Lower priority for ${task.task_type}`} className="secondary" disabled={busy === `task-${task.id}` || !editableTaskPriority(task)} onClick={() => void onPriority(task, task.priority - 10)} type="button">-10</button><button aria-label={`Raise priority for ${task.task_type}`} disabled={busy === `task-${task.id}` || !editableTaskPriority(task)} onClick={() => void onPriority(task, task.priority + 10)} type="button">+10</button></div></td><td>{task.attempt_count}</td><td>{task.leased_by ?? "--"}</td><td>{formatDate(task.created_at)}</td></tr>)}{end < tasks.length && <tr aria-hidden="true"><td colSpan={8} className="virtual-spacer" style={{ height: (tasks.length - end) * rowHeight }} /></tr>}</tbody></table></div>;
}

type WorkersPageProps = {
  onOpenQueue: () => void;
  systemHealth: SystemHealth | null;
  tasks: Task[];
};

export function WorkersPage({ onOpenQueue, systemHealth, tasks }: WorkersPageProps) {
  const { formatDate } = useTranslation();
  const activeTasks = tasks.filter((task) => ["leased", "running"].includes(task.status));
  const workers = new Set(activeTasks.map((task) => task.leased_by).filter((worker): worker is string => Boolean(worker)));
  const activeLabel = `${activeTasks.length} active lease${activeTasks.length === 1 ? "" : "s"}`;
  const queueContext = systemHealth ? `${systemHealth.queue.pending} pending tasks · ${systemHealth.queue.active} active tasks` : "Queue health is unavailable until the service responds.";

  return <div className="workspace-page workers-page">
    <PageHeader description="Track active task leases and the worker capacity currently consuming evaluation work." eyebrow="Operations" status={<>{activeLabel}</>} title="Workers" />
    {activeTasks.length === 0 ? <WorkspacePanel className="workspace-worker-empty" description="No worker has an active lease at the moment. Inspect the queue and system health before changing deployment capacity." title="No active worker leases" toolbar={<span className="workspace-count">{queueContext}</span>}>
      <button className="secondary" onClick={onOpenQueue} type="button">Open task queue</button>
    </WorkspacePanel> : <>
      <div className="workspace-worker-metrics"><WorkspacePanel title="Active leases"><strong>{activeTasks.length}</strong><span>Tasks currently leased or running</span></WorkspacePanel><WorkspacePanel title="Connected workers"><strong>{workers.size}</strong><span>Distinct workers with an active lease</span></WorkspacePanel><WorkspacePanel title="Queue health"><strong>{systemHealth?.queue.pending ?? "--"}</strong><span>{systemHealth ? "Pending tasks reported by system health" : "Health signal unavailable"}</span></WorkspacePanel></div>
      <WorkspacePanel description="Lease expiry is recorded with each task so stalled workers can be diagnosed without altering queue state." title="Active worker leases" toolbar={<span className="workspace-count">{workers.size} workers</span>}>
        <div className="table-wrap workspace-dense-table workspace-worker-table"><table><thead><tr><th>Worker</th><th>Task</th><th>Run</th><th>State</th><th>Lease expiry</th></tr></thead><tbody>{activeTasks.map((task) => <tr key={task.id}><td>{task.leased_by ?? "--"}</td><td>{task.task_type}</td><td>{task.run_id.slice(0, 8)}</td><td><span className={`badge ${task.status}`}>{task.status.replaceAll("_", " ")}</span></td><td>{formatDate(task.lease_expires_at)}</td></tr>)}</tbody></table></div>
      </WorkspacePanel>
    </>}
  </div>;
}
