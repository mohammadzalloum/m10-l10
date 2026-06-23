import { useEffect } from "react";
import { useRouter } from "next/router";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("access_token");

    if (token) {
      router.replace("/extract");
      return;
    }

    router.replace("/login");
  }, [router]);

  return (
    <main>
      <h1>M10 Recipe Service — Demo</h1>
      <p>Redirecting...</p>
    </main>
  );
}
