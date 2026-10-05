import type { ResearchTask, RoutingDecision } from "./types";

export interface IterationGroup {
  iteration: number;
  tasks: ResearchTask[];
  routing: RoutingDecision | undefined;
}

/** Groups research tasks by iteration and pairs each group with the routing decision that ended it. */
export function groupByIteration(tasks: readonly ResearchTask[], routing: readonly RoutingDecision[]): IterationGroup[] {
  const iterations = new Set<number>([...tasks.map((t) => t.iteration), ...routing.map((r) => r.iteration)]);
  return [...iterations]
    .sort((a, b) => a - b)
    .map((iteration) => ({
      iteration,
      tasks: tasks.filter((t) => t.iteration === iteration),
      routing: routing.find((r) => r.iteration === iteration),
    }));
}

export function countByStatus(tasks: readonly ResearchTask[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const t of tasks) out[t.status] = (out[t.status] ?? 0) + 1;
  return out;
}
