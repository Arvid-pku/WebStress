import dynamic from "next/dynamic";
import fs from "fs";
import path from "path";

const TrajectoryPage = dynamic(
  () => import("./TrajectoryPage"),
);

export const dynamicParams = false;

export async function generateStaticParams() {
  try {
    const summaryPath = path.join(process.cwd(), "public", "results", "summary.json");
    const summary = JSON.parse(fs.readFileSync(summaryPath, "utf-8"));
    return (summary.tasks || []).map((t: { task_id: string }) => ({
      taskId: t.task_id,
    }));
  } catch {
    return [];
  }
}

export default async function Page({ params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = await params;
  return <TrajectoryPage taskId={taskId} />;
}
