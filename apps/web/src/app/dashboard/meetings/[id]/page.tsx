"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchAPI } from "@/lib/api";

type ActionItem = {
  id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
};

type Report = {
  id: string;
  status: string;
  summary: string;
  conclusion: string;
  decisions: string[];
  risks: string[];
  blockers: string[];
  tags: string[];
  action_items: ActionItem[];
};

type Meeting = {
  id: string;
  title: string;
  meet_url: string;
  status: string;
};

export default function MeetingDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [startingBot, setStartingBot] = useState(false);

  useEffect(() => {
    loadData();
    
    // Poll every 5 seconds to auto-update status when meeting is active
    const intervalId = setInterval(() => {
      setMeeting((currentMeeting) => {
        // Only poll if we don't have a meeting yet, or if it's in an active state
        if (!currentMeeting || !["COMPLETED", "FAILED", "CANCELLED"].includes(currentMeeting.status)) {
          loadData(true); // pass true to indicate silent background load
        }
        return currentMeeting;
      });
    }, 5000);

    return () => clearInterval(intervalId);
  }, [id]);

  const loadData = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const meetData = await fetchAPI(`/meetings/${id}`);
      setMeeting(meetData);

      try {
        const reportData = await fetchAPI(`/meetings/${id}/report`);
        setReport(reportData);
      } catch (err) {
        setReport(null);
      }
    } catch (err) {
      console.error(err);
      router.push("/dashboard");
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const regenerateReport = async () => {
    setGenerating(true);
    try {
      await fetchAPI(`/meetings/${id}/report/regenerate`, { method: "POST" });
      alert("Report generation started! Check back in a few minutes.");
      loadData();
    } catch (err) {
      alert("Failed to regenerate report");
    } finally {
      setGenerating(false);
    }
  };

  const handleStartBot = async () => {
    setStartingBot(true);
    try {
      await fetchAPI(`/meetings/${id}/start-bot`, { method: "POST" });
      alert("Bot has been dispatched!");
      loadData();
    } catch (err) {
      alert("Failed to start bot");
    } finally {
      setStartingBot(false);
    }
  };

  const handleExportPDF = async () => {
    try {
      await fetchAPI(`/meetings/${id}/report/pdf`, { method: "POST" });
      alert("PDF generation started in the background!");
    } catch (err) {
      alert("Failed to start PDF generation");
    }
  };

  const handleDeleteMeeting = async () => {
    if (!confirm("Are you sure you want to delete this meeting?")) return;
    try {
      await fetchAPI(`/meetings/${id}`, { method: "DELETE" });
      router.push("/dashboard");
    } catch (err) {
      alert("Failed to delete meeting");
    }
  };

  const handleStopBot = async () => {
    if (!confirm("Are you sure you want to stop the bot?")) return;
    try {
      await fetchAPI(`/meetings/${id}/stop-bot`, { method: "POST" });
      alert("Bot stopped successfully");
      loadData();
    } catch (err) {
      alert("Failed to stop bot");
    }
  };

  if (loading) return <div>Loading...</div>;
  if (!meeting) return <div>Meeting not found</div>;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="bg-white p-6 rounded-lg shadow-sm border dark:bg-gray-800 dark:border-gray-700 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{meeting.title}</h1>
          <a href={meeting.meet_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
            {meeting.meet_url}
          </a>
          <div className="mt-2 text-sm text-gray-500">Status: {meeting.status}</div>
        </div>
        <div className="space-x-3">
          <button
            onClick={handleExportPDF}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-700"
          >
            Export PDF
          </button>
          {!["COMPLETED", "FAILED", "CANCELLED", "SCHEDULED", "PROCESSING_TRANSCRIPT", "GENERATING_REPORT"].includes(meeting.status) && (
            <button
              onClick={handleStopBot}
              className="px-4 py-2 text-sm font-medium text-white bg-orange-600 rounded-md hover:bg-orange-700"
            >
              Stop Bot
            </button>
          )}
          <button
            onClick={handleStartBot}
            disabled={startingBot || !["SCHEDULED", "FAILED", "CANCELLED", "COMPLETED", "GENERATING_REPORT"].includes(meeting.status)}
            className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {startingBot ? "Starting..." : "Start Bot"}
          </button>
          <button
            onClick={regenerateReport}
            disabled={generating}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            Regenerate AI Report
          </button>
          <button
            onClick={handleDeleteMeeting}
            className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700"
          >
            Delete
          </button>
        </div>
      </div>

      {!report && meeting.status === "COMPLETED" && (
        <div className="bg-yellow-50 p-6 rounded-lg border border-yellow-200 dark:bg-yellow-900/20 dark:border-yellow-800">
          <p className="text-yellow-800 dark:text-yellow-200">No report generated yet. Click "Regenerate AI Report" to create one.</p>
        </div>
      )}

      {report && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 space-y-6">
            <div className="bg-white p-6 rounded-lg shadow-sm border dark:bg-gray-800 dark:border-gray-700">
              <h2 className="text-xl font-bold mb-4 dark:text-white">Executive Summary</h2>
              <p className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{report.summary}</p>
            </div>
            
            <div className="bg-white p-6 rounded-lg shadow-sm border dark:bg-gray-800 dark:border-gray-700">
              <h2 className="text-xl font-bold mb-4 dark:text-white">Conclusion</h2>
              <p className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{report.conclusion}</p>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-sm border dark:bg-gray-800 dark:border-gray-700">
              <h2 className="text-xl font-bold mb-4 dark:text-white">Action Items</h2>
              {report.action_items.length === 0 ? (
                <p className="text-gray-500">No action items detected.</p>
              ) : (
                <ul className="space-y-4">
                  {report.action_items.map((item) => (
                    <li key={item.id} className="p-4 bg-gray-50 rounded-md border dark:bg-gray-700 dark:border-gray-600">
                      <div className="flex justify-between items-start">
                        <h4 className="font-semibold text-gray-900 dark:text-white">{item.title}</h4>
                        <span className="text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded-full dark:bg-blue-900/30 dark:text-blue-300">
                          {item.priority}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mt-1 dark:text-gray-400">{item.description}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="space-y-6">
            <div className="bg-white p-6 rounded-lg shadow-sm border dark:bg-gray-800 dark:border-gray-700">
              <h3 className="font-bold mb-3 dark:text-white">Key Decisions</h3>
              <ul className="list-disc pl-5 text-gray-700 dark:text-gray-300 text-sm space-y-1">
                {report.decisions.map((d, i) => <li key={i}>{d}</li>)}
              </ul>
            </div>
            
            <div className="bg-white p-6 rounded-lg shadow-sm border dark:bg-gray-800 dark:border-gray-700">
              <h3 className="font-bold mb-3 dark:text-white">Risks & Blockers</h3>
              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-semibold text-red-600 dark:text-red-400">Risks</h4>
                  <ul className="list-disc pl-5 text-gray-700 dark:text-gray-300 text-sm mt-1">
                    {report.risks.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-orange-600 dark:text-orange-400">Blockers</h4>
                  <ul className="list-disc pl-5 text-gray-700 dark:text-gray-300 text-sm mt-1">
                    {report.blockers.map((b, i) => <li key={i}>{b}</li>)}
                  </ul>
                </div>
              </div>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-sm border dark:bg-gray-800 dark:border-gray-700">
              <h3 className="font-bold mb-3 dark:text-white">Tags</h3>
              <div className="flex flex-wrap gap-2">
                {report.tags.map((tag, i) => (
                  <span key={i} className="px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded-full border dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
