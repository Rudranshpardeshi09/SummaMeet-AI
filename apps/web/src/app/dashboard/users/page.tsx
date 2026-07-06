"use client";

import { useEffect, useState } from "react";
import { fetchAPI } from "@/lib/api";

type User = {
  id: string;
  email: string;
  name: string | null;
  role: string;
  status: string;
  created_at: string;
};

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviting, setInviting] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [inviteLink, setInviteLink] = useState("");

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      const data = await fetchAPI("/users");
      setUsers(data.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviting(true);
    setInviteLink("");
    try {
      const res = await fetchAPI("/users", {
        method: "POST",
        body: JSON.stringify({
          email: inviteEmail,
          name: inviteName || undefined,
          role: inviteRole,
        }),
      });
      setInviteLink(res.invite_url);
      setInviteEmail("");
      setInviteName("");
      await loadUsers();
    } catch (err: any) {
      alert(err.message || "Failed to invite user");
    } finally {
      setInviting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to remove this user?")) return;
    try {
      await fetchAPI(`/users/${id}`, { method: "DELETE" });
      await loadUsers();
    } catch (err: any) {
      alert(err.message || "Failed to remove user");
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="bg-white p-6 rounded-lg shadow-sm border dark:bg-gray-800 dark:border-gray-700">
        <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">Invite New User</h3>
        <form onSubmit={handleInvite} className="flex gap-4 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label>
            <input
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
            />
          </div>
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name (Optional)</label>
            <input
              type="text"
              value={inviteName}
              onChange={(e) => setInviteName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
            />
          </div>
          <div className="w-48">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Role</label>
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
            >
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={inviting}
            className="px-4 py-2 font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 h-[42px]"
          >
            {inviting ? "Inviting..." : "Send Invite"}
          </button>
        </form>
        {inviteLink && (
          <div className="mt-4 p-4 bg-green-50 text-green-800 rounded-md border border-green-200 dark:bg-green-900/20 dark:text-green-300 dark:border-green-800">
            User invited successfully! Share this link with them:
            <div className="mt-2 font-mono bg-white dark:bg-black/20 p-2 rounded border border-green-200 break-all select-all">
              {inviteLink}
            </div>
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg shadow-sm border overflow-hidden dark:bg-gray-800 dark:border-gray-700">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-900">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">User</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Role</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Joined</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200 dark:bg-gray-800 dark:divide-gray-700">
            {loading ? (
              <tr><td colSpan={5} className="px-6 py-4 text-center text-sm text-gray-500">Loading users...</td></tr>
            ) : users.length === 0 ? (
              <tr><td colSpan={5} className="px-6 py-4 text-center text-sm text-gray-500">No users found.</td></tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900 dark:text-white">{u.name || "N/A"}</div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">{u.email}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    <span className="capitalize">{u.role}</span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      u.status === 'ACTIVE' 
                        ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
                        : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300'
                    }`}>
                      {u.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-3">
                    <button onClick={() => handleDelete(u.id)} className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300">
                      Remove
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
