import { ArrowDown, ArrowUp, ChevronDown, EyeOff, Settings2 } from "lucide-react";
import { hideColumnAction } from "@/app/actions";
import type { TablePage } from "@/lib/columns";
import type { MenuItem, Params, SortDir } from "@/lib/filters";

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

/** The view's other params as hidden fields, so a form in a bar or a menu changes only its own. */
export function Kept({ params, except }: { params: Params; except: string }) {
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

/** What a header's menu holds (PRO-572): the column's sorts, its filters, its keyword search, Hide column. */
export type HeaderMenu = {
  sorts?: MenuItem[];
  groups?: MenuGroup[];
  active?: boolean;
  search?: { action: string; name: string; value: string; params: Params; placeholder: string };
  hide?: { page: TablePage; key: string };
};

/**
 * A column header (PRO-558, PRO-572): its name sorts the table by the column, and again reverses it.
 * The 20px button beside it opens the column's menu: its sorts, its filters and keyword search, Hide
 * column, and Table settings. The button carries the accent while one of the column's filters is set.
 * Links and GET forms only, so every view can be shared.
 */
export function HeaderCell({ label, sort, menu, className, tableSettings = true }: {
  label: string;
  sort?: { href: string; active: boolean; dir: SortDir };
  menu?: HeaderMenu;
  className?: string;
  tableSettings?: boolean;
}) {
  return (
    <th className={className} aria-sort={sort?.active ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}>
      <span className="th">
        {sort ? (
          <a className={sort.active ? "th-sort active" : "th-sort"} href={sort.href} title={`Sort by ${label}`}>
            {label}
            {sort.active ? sort.dir === "asc" ? <ArrowUp aria-hidden="true" /> : <ArrowDown aria-hidden="true" /> : null}
          </a>
        ) : (
          <span>{label}</span>
        )}
        {menu || tableSettings ? (
        <details className="menu">
          <summary className={menu?.active ? "th-filter active" : "th-filter"} aria-label={`Menu for ${label}`} title={`Sort, filter and more: ${label}`}>
            <ChevronDown aria-hidden="true" />
          </summary>
          <div className="menu-body">
            {menu?.sorts?.length ? <MenuLinks groups={[{ title: "Sort", items: menu.sorts }]} /> : null}
            {menu?.groups?.length ? <MenuLinks groups={menu.groups} /> : null}
            {menu?.search ? (
              <form action={menu.search.action} className="menu-group menu-search">
                <Kept params={menu.search.params} except={menu.search.name} />
                <p className="menu-title">Search</p>
                <input
                  type="search"
                  name={menu.search.name}
                  defaultValue={menu.search.value}
                  placeholder={menu.search.placeholder}
                  aria-label={`Search ${label}`}
                />
              </form>
            ) : null}
            <div className="menu-group">
              {menu?.hide ? (
                <form action={hideColumnAction}>
                  <input type="hidden" name="page" value={menu.hide.page} />
                  <input type="hidden" name="key" value={menu.hide.key} />
                  <button type="submit" className="menu-item">
                    <EyeOff aria-hidden="true" />
                    Hide column
                  </button>
                </form>
              ) : null}
              {tableSettings ? (
                <button type="button" className="menu-item" data-opens="table-settings">
                  <Settings2 aria-hidden="true" />
                  Table settings
                </button>
              ) : null}
            </div>
          </div>
        </details>
        ) : null}
      </span>
    </th>
  );
}
