// Past work to build on (P6, PW11, phase 6b): the Proposal Library's index the worker keeps in drive_items, grouped
// for Start the draft and the Outline. The dashboard never calls Google. No imports, so `node --test` can load it.

export type PastWorkItem = {
  id: string;
  name: string;
  path: string | null;
  mime: string | null;
  web_link: string | null;
  modified_at: string | null;
};

const FOLDER = "application/vnd.google-apps.folder";
const SUBMISSION = /^Submissions\/[^/]+$/;
const REFERENCE = /^01 Company Reference\//;

/** The library's portal slugs (docs/LIBRARY_CONVENTIONS.md) as the dashboard names the portals. */
const PORTALS: Record<string, string> = {
  "vulcan-sof": "Vulcan SOF", "ssc-front-door": "SSC Front Door", "sam-gov": "SAM.gov", nstxl: "NSTXL", diu: "DIU",
  afwerx: "AFWERX", iarpa: "IARPA", "space-force": "Space Force", "doe-sbir": "DOE SBIR", "bidnet-co": "BidNet CO",
  "bidnet-fl": "BidNet FL", dsip: "DSIP", apfit: "APFIT", xtech: "xTech", antx: "ANTX", tencap: "TENCAP",
  sofwerx: "SOFWERX", sparx: "SPARX", "nasa-sbir": "NASA SBIR", "dhs-sbir": "DHS SBIR", piee: "PIEE", tacfi: "TACFI",
  other: "Other",
};
/** A folder's name with an undated (nodate_) folder's date written lowest, so it sorts after every dated one. */
const dated = (name: string) => name.replace(/^nodate_/, "0000-00-00_");

/** A submission by its title, portal and date; a reference file by its name and the folder it is in. */
export function pastWorkLabel(item: PastWorkItem): string {
  const folder = /^(\d{4}-\d{2}-\d{2}|nodate)_([a-z0-9-]+?)_([a-z0-9-]+)$/.exec(item.name);
  if (item.mime === FOLDER && folder) {
    const words = folder[3].replace(/-/g, " ");
    return `${words[0].toUpperCase()}${words.slice(1)}, ${PORTALS[folder[2]] ?? folder[2]}, ${folder[1] === "nodate" ? "no date" : folder[1]}`;
  }
  const parts = (item.path ?? "").split("/");
  return parts.length > 2 ? `${item.name} (${parts[parts.length - 2]})` : item.name;
}

/** Past submissions, newest first, then the company reference files; anything chosen already is left out. */
export function pastWorkGroups(items: PastWorkItem[], chosen: string[]): { title: string; items: PastWorkItem[] }[] {
  const open = items.filter((i) => !chosen.includes(i.id));
  const groups = [
    { title: "Past submissions", items: open.filter((i) => i.mime === FOLDER && SUBMISSION.test(i.path ?? "")).sort((a, b) => dated(b.name).localeCompare(dated(a.name))) },
    { title: "Company reference", items: open.filter((i) => i.mime !== FOLDER && REFERENCE.test(i.path ?? "")).sort((a, b) => (a.path ?? "").localeCompare(b.path ?? "")) },
  ];
  return groups.filter((g) => g.items.length);
}
