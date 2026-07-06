"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { fetchAPI } from "@/lib/api";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAPI("/users/me")
      .then((data) => setUser(data))
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) return <div className="flex items-center justify-center h-screen">Loading...</div>;
  if (!user) return null;

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      <aside className="w-64 bg-white border-r dark:bg-gray-800 dark:border-gray-700">
        <div className="p-6">
          <h2 className="text-xl font-bold text-gray-800 dark:text-white">AI Note Taker</h2>
        </div>
        <nav className="mt-6">
          <Link
            href="/dashboard"
            className={`block px-6 py-3 text-sm font-medium ${
              pathname === "/dashboard"
                ? "bg-gray-100 text-blue-600 dark:bg-gray-700 dark:text-blue-400"
                : "text-gray-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700"
            }`}
          >
            Meetings
          </Link>
          <Link
            href="/dashboard/action-items"
            className={`block px-6 py-3 text-sm font-medium ${
              pathname === "/dashboard/action-items"
                ? "bg-gray-100 text-blue-600 dark:bg-gray-700 dark:text-blue-400"
                : "text-gray-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700"
            }`}
          >
            Action Items
          </Link>
          {user?.role === "admin" && (
            <Link
              href="/dashboard/users"
              className={`block px-6 py-3 text-sm font-medium ${
                pathname === "/dashboard/users"
                  ? "bg-gray-100 text-blue-600 dark:bg-gray-700 dark:text-blue-400"
                  : "text-gray-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700"
              }`}
            >
              Users
            </Link>
          )}
        </nav>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="flex items-center justify-between px-6 py-4 bg-white border-b dark:bg-gray-800 dark:border-gray-700">
          <div className="text-xl font-semibold text-gray-800 dark:text-white">
            {pathname.includes("/users") ? "User Management" : pathname.includes("/action-items") ? "Action Items" : "Meetings"}
          </div>
          <div className="flex items-center gap-4">
            <div className="text-sm text-gray-600 dark:text-gray-300">
              {user.email}
            </div>
            <button
              onClick={() => {
                localStorage.removeItem("auth_token");
                router.push("/login");
              }}
              className="text-sm font-medium text-red-600 hover:underline dark:text-red-400"
            >
              Sign out
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
