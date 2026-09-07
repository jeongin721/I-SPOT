import { createBrowserRouter, Navigate } from "react-router";
import AppLayout from "./AppLayout";
import LoginPage from "./LoginPage";
import NotFoundPage from "../pages/NotFoundPage";
import PermissionDeniedPage from "../pages/PermissionDeniedPage";

// Lazy imports to keep bundle sane
import DashboardView from "../views/DashboardView";
import CasesView from "../views/CasesView";
import CaseDetailPage from "../pages/CaseDetailPage";
import PreSessionPage from "../pages/PreSessionPage";
import STTCaseSelectorPage from "../pages/STTCaseSelectorPage";
import SessionListPage from "../pages/SessionListPage";
import AIAnalysisSelectorPage from "../pages/AIAnalysisSelectorPage";
import AIAnalysisListPage from "../pages/AIAnalysisListPage";
import AccountPage from "../pages/AccountPage";
import CaseSelectorListPage from "../pages/CaseSelectorListPage";
import TranscriptReviewView from "../views/TranscriptReviewView";
import AIReviewView from "../views/AIReviewView";
import CasePlanView from "../views/CasePlanView";
import ClosureView from "../views/ClosureView";
import ReportView from "../views/ReportView";
import RecordingView from "../views/RecordingView";

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", element: <DashboardView /> },
      { path: "cases", element: <CasesView /> },
      { path: "cases/:caseId", element: <CaseDetailPage /> },
      { path: "cases/:caseId/counseling/new", element: <PreSessionPage /> },
      { path: "cases/:caseId/sessions", element: <SessionListPage /> },
      { path: "cases/:caseId/sessions/:sessionId/transcript", element: <TranscriptReviewView /> },
      { path: "cases/:caseId/analyses", element: <AIAnalysisListPage /> },
      { path: "cases/:caseId/analyses/:analysisId", element: <AIReviewView /> },
      { path: "cases/:caseId/plan", element: <CasePlanView /> },
      { path: "cases/:caseId/closure", element: <ClosureView /> },
      { path: "cases/:caseId/reports", element: <ReportView /> },
      { path: "cases/:caseId/recording", element: <RecordingView /> },
      { path: "recording", element: <RecordingView /> },
      { path: "stt-cases", element: <STTCaseSelectorPage /> },
      { path: "ai-cases", element: <AIAnalysisSelectorPage /> },
      { path: "plan-cases", element: <CaseSelectorListPage mode="plan" /> },
      { path: "closure-cases", element: <CaseSelectorListPage mode="closure" /> },
      { path: "report-cases", element: <CaseSelectorListPage mode="report" /> },
      { path: "profile", element: <AccountPage /> },
      { path: "forbidden", element: <PermissionDeniedPage /> },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
]);
