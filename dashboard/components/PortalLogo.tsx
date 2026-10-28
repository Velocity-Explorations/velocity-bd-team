import { portalLogo } from "@/lib/home";

/** The portal's logo on a white 40px tile, or its initials where it has none. The name is written beside it. */
export function PortalLogo({ portal }: { portal: string }) {
  const logo = portalLogo(portal);
  return "src" in logo ? (
    <span className="logo-tile">
      <img src={logo.src} alt="" width={32} height={32} />
    </span>
  ) : (
    <span className="logo-tile initials" aria-hidden="true">
      {logo.initials}
    </span>
  );
}
