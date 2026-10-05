import type { Metadata } from "next";
import { Workspace } from "@/components/workspace/Workspace";

export const metadata: Metadata = { title: "Investigation workspace" };

export default async function InvestigationPage(props: PageProps<"/investigations/[id]">) {
  const { id } = await props.params;
  return <Workspace id={id} />;
}
