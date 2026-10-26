import { MenuLinks, type MenuGroup } from "@/components/HeaderCell";
import { choiceLinks, filterHref, type CallState, type Params, type PortalOption } from "@/lib/filters";
import { optionGroups, type TagOption } from "@/lib/tags";

const STATES: { value: CallState; label: string }[] = [
  { value: "", label: "All" },
  { value: "open", label: "Open" },
  { value: "closed", label: "Closed" },
];

/** The view's other params as hidden fields, so a form in the bar changes only its own. */
function Kept({ params, except }: { params: Params; except: string }) {
  return (
    <>
      {Object.entries(params)
        .filter(([key]) => key !== except)
        .flatMap(([key, value]) => (typeof value === "string" ? [value] : value).filter(Boolean).map((item) => [key, item]))
        .map(([key, item]) => (
          <input key={`${key}=${item}`} type="hidden" name={key} value={item} />
        ))}
    </>
  );
}

/**
 * The filters that span the whole table, in a row above it (PRO-558): title search on All calls,
 * portals, tag, and open or closed. Choices apply at once; the Portals menu applies when it closes
 * (MenuController), or with its Apply button. Column filters live in the column headers.
 */
export function FilterBar(props: {
  action: string;
  params: Params;
  portals: PortalOption[];
  selected: string[];
  tags: TagOption[];
  tag: string;
  state: CallState;
  search?: string;
  filtered: boolean;
}) {
  const chosen = props.selected.length === 0 ? "All" : props.selected.length === 1 ? props.selected[0] : `${props.selected.length} chosen`;
  const tagGroups: MenuGroup[] = [
    { items: choiceLinks(props.action, props.params, "tag", [{ value: "", label: "Any" }], props.tag) },
    ...optionGroups(props.tags).map((group) => ({
      title: group.label,
      items: choiceLinks(props.action, props.params, "tag", group.names.map((name) => ({ value: name, label: name })), props.tag),
    })),
  ];
  return (
    <div className="filter-bar" role="search" aria-label="Filters">
      {props.search !== undefined ? (
        <form action={props.action}>
          <Kept params={props.params} except="q" />
          <input type="search" name="q" defaultValue={props.search} placeholder="Title contains" aria-label="Title contains" />
        </form>
      ) : null}
      <details className="menu" data-apply-on-close="">
        <summary>Portals: {chosen}</summary>
        <div className="menu-body">
          <form action={props.action}>
            <Kept params={props.params} except="portal" />
            {props.portals.length === 0 ? <p className="hint">No portals scanned yet.</p> : null}
            {props.portals.map(({ name, calls }) => (
              <label key={name} className={calls === 0 ? "check no-calls" : "check"} title={calls === 0 ? "Scanned, but nothing is stored yet" : undefined}>
                <input type="checkbox" name="portal" value={name} defaultChecked={props.selected.includes(name)} /> {name}
                <span className="count" aria-label={`${calls} calls`}>{calls}</span>
              </label>
            ))}
            <p className="hint">None ticked shows every portal. Applies when this menu closes.</p>
            <button type="submit">Apply</button>
          </form>
        </div>
      </details>
      {props.tags.length ? (
        <details className="menu">
          <summary>Tag: {props.tag || "Any"}</summary>
          <div className="menu-body">
            <MenuLinks groups={tagGroups} />
          </div>
        </details>
      ) : null}
      <nav className="segmented" aria-label="Open or closed">
        {STATES.map((s) => (
          <a key={s.label} href={filterHref(props.action, { ...props.params, state: s.value })} className={props.state === s.value ? "active" : undefined}>
            {s.label}
          </a>
        ))}
      </nav>
      {props.filtered ? (
        <a href={props.action} className="reset">
          Clear filters
        </a>
      ) : null}
    </div>
  );
}
