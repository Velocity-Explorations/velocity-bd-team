import { NextResponse, type NextRequest } from "next/server";
import { googleKeys, IAP_HEADER, needsSignIn, verifyIapToken } from "@/lib/iap";

// Behind Google's IAP (DASHBOARD_IAP_AUDIENCE set), every request must carry IAP's signed header,
// except the load balancer's health check. A request that reached the container some other way
// sees nothing. Without the setting this lets everything through, as on the scan PC.

export async function proxy(request: NextRequest): Promise<NextResponse> {
  const audience = process.env.DASHBOARD_IAP_AUDIENCE?.trim();
  if (!audience || !needsSignIn(request.nextUrl.pathname)) return NextResponse.next();
  const verified = await verifyIapToken(request.headers.get(IAP_HEADER), audience, googleKeys());
  if (verified.ok) return NextResponse.next();
  console.warn(`Refused ${request.nextUrl.pathname}: ${verified.reason}`);
  return new NextResponse("Open the dashboard through the company sign-in.", {
    status: 401,
    headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" },
  });
}
