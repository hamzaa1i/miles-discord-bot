import { redirect } from 'next/navigation';

/**
 * /roles — legacy route. The old four-tab roles page was split into
 * dedicated routes (autorole, self-roles, color-roles, onboarding), so
 * old bookmarks land on the autorole page instead of a dead end.
 */
export default function RolesRedirect({ params }: { params: { guildId: string } }) {
  redirect(`/servers/${params.guildId}/autorole`);
}
