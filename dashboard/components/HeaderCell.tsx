import { ArrowDown, ArrowUp, ChevronDown } from "lucide-react";
import type { MenuItem, SortDir } from "@/lib/filters";

export type MenuGroup = { title?: string; items: MenuItem[] };

/** A menu's choices as links, in titled groups. */
export function MenuLinks({ groups }: { groups: MenuGroup[] }) {
  return (
    <>
      {groups.map((group, i) => (
        <div key={group.title ?? i} className="menu-group">
          {group.title ? <p className="menu-title">{group.title}</p> : null}
          {group.items.map((item) => (
            <a key={item.label} href={item.href} className={item.active ? "active" : undefined} aria-current={item.active ? "true" : undefined}>
              {item.label}
            </a>
          ))}
        </div>
      ))}
    </>
  );
}

/**
 * A column header (PRO-558): its name sorts the table by the column, and again reverses it; the
 * button beside it opens the column's own filter, when it has one. Links only, so every view can be
 * shared.
 */
export function HeaderCell({ label, sort, menu }: {
  label: string;
  sort?: { href: string; active: boolean; dir: SortDir };
  menu?: { active: boolean; groups: MenuGroup[] };
}) {
  return (
    <th aria-sort={sort?.active ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}>
      <span className="th">
        {sort ? (
          <a className={sort.active ? "th-sort active" : "th-sort"} href={sort.href} title={`Sort by ${label}`}>
            {label}
            {sort.active ? sort.dir === "asc" ? <ArrowUp aria-hidden="true" /> : <ArrowDown aria-hidden="true" /> : null}
          </a>
        ) : (
          label
        )}
        {menu ? (
          <details className="menu">
            <summary className={menu.active ? "th-filter active" : "th-filter"} aria-label={`Filter ${label}`} title={`Filter ${label}`}>
              <ChevronDown aria-hidden="true" />
            </summary>
            <div className="menu-body">
              <MenuLinks groups={menu.groups} />
            </div>
          </details>
        ) : null}
      </span>
    </th>
  );
}
