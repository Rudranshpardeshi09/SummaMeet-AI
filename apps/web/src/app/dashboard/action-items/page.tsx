"use client";

import { useEffect, useState } from "react";
import { fetchAPI } from "@/lib/api";

type ActionItem = {
  id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  meeting_id: string;
};

export default function ActionItemsPage() {
  const [items, setItems] = useState<ActionItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadItems();
  }, []);

  const loadItems = async () => {
    try {
      const data = await fetchAPI("/action-items");
      setItems(data.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const updateStatus = async (id: string, newStatus: string) => {
    try {
      await fetchAPI(`/action-items/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
      loadItems();
    } catch (err) {
      alert("Failed to update status");
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="bg-white rounded-lg shadow-sm border overflow-hidden dark:bg-gray-800 dark:border-gray-700">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-900">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Task</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Description</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Priority</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Status</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200 dark:bg-gray-800 dark:divide-gray-700">
            {loading ? (
              <tr><td colSpan={4} className="px-6 py-4 text-center text-sm text-gray-500">Loading action items...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={4} className="px-6 py-4 text-center text-sm text-gray-500">No action items found.</td></tr>
            ) : (
              items.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-6 py-4 text-sm font-medium text-gray-900 dark:text-white">{item.title}</td>
                  <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400 max-w-xs truncate">{item.description}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      item.priority === 'HIGH' || item.priority === 'CRITICAL' ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300' :
                      item.priority === 'MEDIUM' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300' :
                      'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
                    }`}>
                      {item.priority || 'NORMAL'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <select
                      value={item.status}
                      onChange={(e) => updateStatus(item.id, e.target.value)}
                      className="block w-full pl-3 pr-10 py-1 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                    >
                      <option value="NOT_STARTED">Not Started</option>
                      <option value="IN_PROGRESS">In Progress</option>
                      <option value="DONE">Done</option>
                    </select>
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
