import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { isReport, type AnalysisResponse, type Report } from "../api/types";
import { ErrorAlert } from "../components/Feedback";
import { ProgressPanel } from "../components/ProgressPanel";
import { viewerCode, BreakdownTab } from "../components/report/BreakdownTab";
import { FeedbackWidget } from "../components/report/FeedbackWidget";
import { ImprovedCodeTab } from "../components/report/ImprovedCodeTab";
import { OverviewTab } from "../components/report/OverviewTab";
import { FallbackBanner, ReportHeader } from "../components/report/ReportHeader";
import { ReportTabs, type TabDef, type TabId } from "../components/report/ReportTabs";
import { RisksTab } from "../components/report/RisksTab";
import { SummaryCards } from "../components/report/SummaryCards";
import { TransparencyTab } from "../components/report/TransparencyTab";
import { PageSkeleton } from "../components/Skeleton";
import { getFeedbackToken, getOpenedFindings, setOpenedFindings } from "../utils/storage";

const TAB_IDS: TabId[] = ["overview", "breakdown", "risks", "improved", "transparency"];

export function ReportPage() {
  const { publicId = "" } = useParams();
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: 5 * 60_000 });
  const query = useQuery<AnalysisResponse, ApiError>({
    queryKey: ["analysis", publicId],
    queryFn: () => api.getAnalysis(publicId, getFeedbackToken(publicId)),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "queued" || s === "running" ? 1500 : false;
    },
  });

  useEffect(() => {
    document.title = "Report · Explainable AI Code Review Assistant";
  }, []);

  if (query.isLoading) return <PageSkeleton />;
  if (query.isError) {
    if (query.error.status === 404) {
      const hours = meta.data?.guest_retention_hours ?? 24;
      return (
        <div className="mx-auto max-w-xl space-y-4">
          <ErrorAlert
            title="Report not found"
            message={`This report does not exist or has expired. Guest reports are deleted after ${hours} hours.`}
          />
          <Link to="/" className="btn-primary no-underline">
            Start a new analysis
          </Link>
        </div>
      );
    }
    return <ErrorAlert message={query.error.message} onRetry={() => query.refetch()} />;
  }
  const data = query.data!;
  if (!isReport(data)) {
    if (data.status === "failed") {
      return (
        <div className="mx-auto max-w-xl space-y-4">
          <ErrorAlert
            title="The analysis failed"
            message={data.error_message ?? "Something went wrong while analysing your code."}
          />
          <Link to="/" className="btn-primary no-underline">
            Try again
          </Link>
        </div>
      );
    }
    return <ProgressPanel status={data} />;
  }
  return <CompletedReport report={data} />;
}

function CompletedReport({ report }: { report: Report }) {
  const location = useLocation();
  const navigate = useNavigate();
  const hashTab = location.hash.replace("#", "") as TabId;
  const tab: TabId = TAB_IDS.includes(hashTab) ? hashTab : "overview";

  const [opened, setOpened] = useState<Set<string>>(() => new Set(getOpenedFindings(report.public_id)));
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [focusKey, setFocusKey] = useState<string | null>(null);

  const severityOf = useMemo(
    () => new Map(report.findings.map((f) => [f.key, f.severity])),
    [report.findings],
  );

  const setTab = useCallback(
    (id: TabId) => navigate({ pathname: location.pathname, hash: `#${id}` }, { replace: true }),
    [navigate, location.pathname],
  );

  const toggleFinding = useCallback(
    (key: string, open: boolean) => {
      setExpanded((prev) => {
        const next = new Set(prev);
        if (open) next.add(key);
        else next.delete(key);
        return next;
      });
      // Opening a CRITICAL finding marks it as read (Section 11.5).
      if (open && severityOf.get(key) === "CRITICAL") {
        setOpened((prev) => {
          if (prev.has(key)) return prev;
          const next = new Set(prev).add(key);
          setOpenedFindings(report.public_id, [...next]);
          return next;
        });
      }
    },
    [severityOf, report.public_id],
  );

  const openFinding = useCallback(
    (key: string) => {
      toggleFinding(key, true);
      setFocusKey(key);
      setTab("risks");
    },
    [toggleFinding, setTab],
  );

  useEffect(() => {
    if (focusKey) {
      const id = window.setTimeout(() => setFocusKey(null), 600);
      return () => window.clearTimeout(id);
    }
  }, [focusKey]);

  const tabs: TabDef[] = [
    { id: "overview", label: "Overview" },
    { id: "breakdown", label: "Breakdown" },
    { id: "risks", label: `Risks (${report.findings.length})` },
    { id: "improved", label: "Improved Code" },
    { id: "transparency", label: "Transparency" },
  ];

  return (
    <div className="space-y-5">
      <ReportHeader report={report} />
      <FallbackBanner report={report} />
      <SummaryCards report={report} />
      <ReportTabs tabs={tabs} active={tab} onChange={setTab}>
        {tab === "overview" && <OverviewTab report={report} onOpenFinding={openFinding} />}
        {tab === "breakdown" && <BreakdownTab report={report} />}
        {tab === "risks" && (
          <RisksTab
            findings={report.findings}
            code={viewerCode(report)}
            expanded={expanded}
            onToggle={toggleFinding}
            focusKey={focusKey}
          />
        )}
        {tab === "improved" && (
          <ImprovedCodeTab report={report} opened={opened} onOpenFinding={openFinding} />
        )}
        {tab === "transparency" && <TransparencyTab report={report} />}
      </ReportTabs>
      <FeedbackWidget report={report} />
    </div>
  );
}
