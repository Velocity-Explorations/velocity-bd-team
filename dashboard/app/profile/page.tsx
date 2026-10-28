import type { Metadata } from "next";
import type { ReactNode } from "react";
import { resetProfileAction, saveProfileAction } from "@/app/actions";
import { Shell } from "@/components/Shell";
import { Flash } from "@/components/bits";
import { me } from "@/lib/me";
import { initials } from "@/lib/nav";
import { parseDefaultFilters, TIME_ZONES } from "@/lib/profile";
import { portals, tagOptions } from "@/lib/queries";
import { displayTimeZone } from "@/lib/settings";
import { optionGroups } from "@/lib/tags";
import { firstParam } from "@/lib/text";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Profile settings" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

const STATES = [
  { value: "", label: "All" },
  { value: "open", label: "Open" },
  { value: "closed", label: "Closed" },
];

function Setting({ name, help, children }: { name: string; help: string; children: ReactNode }) {
  return (
    <div className="setting-row">
      <div className="setting-label">
        <p className="setting-name">{name}</p>
        <p className="setting-help">{help}</p>
      </div>
      <div className="setting-field">{children}</div>
    </div>
  );
}

/**
 * Profile settings (U2 to U6, PRO-574): the person's display name and initials, where the dashboard
 * opens, Calls' default filters and their time zone, kept with their name in the ledger so they follow
 * them to any device. Each person edits their own row.
 */
export default async function ProfilePage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const { viewer, profile } = await me();
  const [portalList, tagChoices] = await Promise.all([portals(), tagOptions()]);
  const filters = parseDefaultFilters(profile?.default_filters ?? null);
  const dashboardZone = displayTimeZone();
  const zone = profile?.time_zone ?? "";
  const zones = zone && !TIME_ZONES.includes(zone) ? [...TIME_ZONES, zone] : TIME_ZONES;

  return (
    <Shell section={null}>
      <h1>Profile settings</h1>
      <p className="lead-text muted">Kept with your name in the ledger, so they follow you to any device.</p>
      <Flash notice={firstParam(sp.notice, 300)} error={firstParam(sp.error, 300)} />

      {!viewer ? (
        <div className="empty">
          <p className="title">Log in (top right) to set your profile.</p>
          <p className="muted">Profile settings belong to the person deciding; choose your name in the account menu first.</p>
        </div>
      ) : (
        <form action={saveProfileAction} className="profile-form">
          <Setting name="Name" help="How you appear on votes, notes and the account menu.">
            <div className="name-fields">
              <label className="field">
                <span className="field-label">Display name</span>
                <input type="text" name="display_name" defaultValue={profile?.display_name ?? viewer} maxLength={60} />
              </label>
              <label className="field initials-field">
                <span className="field-label">Initials</span>
                <input type="text" name="initials" defaultValue={profile?.initials ?? ""} maxLength={3} placeholder={initials(profile?.display_name || viewer)} />
              </label>
              <span className="initials big" aria-hidden="true">
                {profile?.initials || initials(profile?.display_name || viewer)}
              </span>
            </div>
          </Setting>

          <Setting name="Signed-in account" help="The Google account you signed in with, shown once Google sign-in is live (PRO-477).">
            <p className="setting-note">
              Not signed in with Google yet. You are deciding as {viewer}; Switch user in the account menu changes that.
            </p>
          </Setting>

          <Setting name="Where the dashboard opens" help="The page you land on when you open the dashboard.">
            <div className="radio-cards">
              <label className="radio-card">
                <input type="radio" name="opens" value="home" defaultChecked={profile?.opens !== "calls"} />
                <span>
                  <strong>Home</strong>
                  <span>What needs attention now</span>
                </span>
              </label>
              <label className="radio-card">
                <input type="radio" name="opens" value="calls" defaultChecked={profile?.opens === "calls"} />
                <span>
                  <strong>Calls</strong>
                  <span>Needs review, your queue to decide</span>
                </span>
              </label>
            </div>
          </Setting>

          <Setting name="Default filters for Calls" help="Calls opens with these. You can still change them on the page, and a shared link's own filters win.">
            <p className="field-label">Portals</p>
            <div className="chip-checks">
              {portalList.map(({ name }) => (
                <label key={name} className="chip-check">
                  <input type="checkbox" name="portal" value={name} defaultChecked={filters.portals.includes(name)} />
                  {name}
                </label>
              ))}
            </div>
            <p className="hint">None ticked shows every portal.</p>
            <div className="filter-fields">
              <label className="field">
                <span className="field-label">Tag</span>
                <select name="tag" defaultValue={filters.tag}>
                  <option value="">Any tag</option>
                  {optionGroups(tagChoices).map((group) => (
                    <optgroup key={group.label} label={group.label}>
                      {group.names.map((name) => (
                        <option key={name} value={name}>
                          {name}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </label>
              <fieldset className="field">
                <legend className="field-label">Open or closed</legend>
                <div className="segmented segmented-radio">
                  {STATES.map((s) => (
                    <label key={s.label}>
                      <input type="radio" name="state" value={s.value} defaultChecked={filters.state === s.value} />
                      {s.label}
                    </label>
                  ))}
                </div>
              </fieldset>
            </div>
          </Setting>

          <Setting name="Time zone" help="Every time on the dashboard shows in this zone. Deadlines a portal wrote as text stay as written.">
            <select name="time_zone" defaultValue={zone} aria-label="Time zone">
              <option value="">{dashboardZone} (dashboard default)</option>
              {zones
                .filter((z) => z !== dashboardZone)
                .map((z) => (
                  <option key={z} value={z}>
                    {z}
                  </option>
                ))}
            </select>
          </Setting>

          <div className="settings-actions profile-actions">
            <button type="submit" formAction={resetProfileAction} className="btn-text">
              Reset to defaults
            </button>
            <a href="/" className="btn">
              Cancel
            </a>
            <button type="submit" className="btn-primary">
              Save
            </button>
          </div>
        </form>
      )}
    </Shell>
  );
}
