"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchAPI } from "@/lib/api";

type Meeting = {
  id: string;
  title: string;
  meeting_url: string;
  status: string;
  created_at: string;
};

export default function DashboardPage() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [overview, setOverview] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // New meeting form
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    loadOverview();
    loadMeetings();
    setupWebSocket();
  }, []);

  const loadOverview = async () => {
    try {
      const data = await fetchAPI("/dashboard/overview");
      setOverview(data);
    } catch (err) {
      console.error(err);
    }
  };

  const setupWebSocket = async () => {
    try {
      const res = await fetchAPI("/ws/ticket", { method: "POST" });
      const ticket = res.ticket;
      const wsUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1')
        .replace('http', 'ws') + `/ws/meetings?ticket=${ticket}`;
      
      const ws = new WebSocket(wsUrl);
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "MEETING_STATUS_UPDATED") {
          setMeetings(prev => prev.map(m => 
            m.id === data.meeting_id ? { ...m, status: data.status } : m
          ));
        }
      };
      return () => ws.close();
    } catch (err) {
      console.error("WS setup failed", err);
    }
  };

  const loadMeetings = async () => {
    try {
      const data = await fetchAPI("/meetings");
      setMeetings(data.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddMeeting = async (e: React.FormEvent) => {
    e.preventDefault();
    setAdding(true);
    try {
      await fetchAPI("/meetings", {
        method: "POST",
        body: JSON.stringify({ title, meeting_url: url }),
      });
      setTitle("");
      setUrl("");
      await loadMeetings();
    } catch (err) {
      alert("Failed to add meeting");
    } finally {
      setAdding(false);
    }
  };

  const handleDeleteMeeting = async (id: string) => {
    if (!confirm("Are you sure you want to delete this meeting?")) return;
    try {
      await fetchAPI(`/meetings/${id}`, { method: "DELETE" });
      await loadMeetings();
    } catch (err) {
      alert("Failed to delete meeting");
    }
  };

  const handleStopBot = async (id: string) => {
    if (!confirm("Are you sure you want to stop the bot?")) return;
    try {
      await fetchAPI(`/meetings/${id}/stop-bot`, { method: "POST" });
      await loadMeetings();
    } catch (err) {
      alert("Failed to stop bot");
    }
  };

  return (
    <div className="space-y-6">
      {/* Overview Stats */}
      {overview && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white p-6 rounded-lg shadow-sm border dark:bg-gray-800 dark:border-gray-700">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Meetings</h3>
            <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{overview.total_meetings}</p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-sm border dark:bg-gray-800 dark:border-gray-700">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Action Items</h3>
            <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{overview.total_action_items}</p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-sm border dark:bg-gray-800 dark:border-gray-700">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Completed Actions</h3>
            <p className="mt-2 text-3xl font-bold text-green-600 dark:text-green-400">{overview.completed_action_items}</p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-sm border dark:bg-gray-800 dark:border-gray-700">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Completion Rate</h3>
            <p className="mt-2 text-3xl font-bold text-blue-600 dark:text-blue-400">{overview.completion_rate_percent}%</p>
          </div>
        </div>
      )}

      <div className="bg-white p-6 rounded-lg shadow-sm border dark:bg-gray-800 dark:border-gray-700">
        <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">Track New Meeting</h3>
        <form onSubmit={handleAddMeeting} className="flex gap-4">
          <input
            type="text"
            placeholder="Meeting Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
          />
          <input
            type="url"
            placeholder="Google Meet URL"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
          />
          <button
            type="submit"
            disabled={adding}
            className="px-4 py-2 font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {adding ? "Adding..." : "Add Meeting"}
          </button>
        </form>
      </div>

      <div className="bg-white rounded-lg shadow-sm border overflow-hidden dark:bg-gray-800 dark:border-gray-700">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-900">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Title</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">URL</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Date</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200 dark:bg-gray-800 dark:divide-gray-700">
            {loading ? (
              <tr><td colSpan={5} className="px-6 py-4 text-center text-sm text-gray-500">Loading meetings...</td></tr>
            ) : meetings.length === 0 ? (
              <tr><td colSpan={5} className="px-6 py-4 text-center text-sm text-gray-500">No meetings found.</td></tr>
            ) : (
              meetings.map((m) => (
                <tr key={m.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">{m.title}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    <a href={m.meeting_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">{m.meeting_url}</a>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                      {m.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {new Date(m.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-3">
                    {!["COMPLETED", "FAILED", "CANCELLED", "SCHEDULED", "PROCESSING_TRANSCRIPT", "GENERATING_REPORT"].includes(m.status) && (
                      <button onClick={() => handleStopBot(m.id)} className="text-orange-600 hover:text-orange-900 dark:text-orange-400 dark:hover:text-orange-300">
                        Stop Bot
                      </button>
                    )}
                    <Link href={`/dashboard/meetings/${m.id}`} className="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300">
                      View Report
                    </Link>
                    <button onClick={() => handleDeleteMeeting(m.id)} className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300">
                      Delete
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
