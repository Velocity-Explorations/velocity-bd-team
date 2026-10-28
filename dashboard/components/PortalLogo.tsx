import { portalLogo } from "@/lib/home";

/** The portal's logo on a white 40px tile (22px when small), or its initials where it has none. The name is written beside it. */
export function PortalLogo({ portal, small = false }: { portal: string; small?: boolean }) {
  const logo = portalLogo(portal);
  return "src" in logo ? (
    <span className={small ? "logo-tile small" : "logo-tile"}>
      <img src={logo.src} alt="" width={small ? 18 : 32} height={small ? 18 : 32} />
    </span>
  ) : (
    <span className={small ? "logo-tile initials small" : "logo-tile initials"} aria-hidden="true">
      {logo.initials}
    </span>
  );
}
