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
import CaseManagementPage from "../pages/CaseManagementPage";
import FollowUpPage from "../pages/FollowUpPage";
import TranscriptReviewView from "../views/TranscriptReviewView";
import AIReviewView from "../views/AIReviewView";
import CasePlanView from "../views/CasePlanView";
import ClosureView from "../views/ClosureView";
import ReportView from "../views/ReportView";
import DocumentWritePage from "../pages/DocumentWritePage";
import AdminApp from "../admin/AdminApp";
export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    // 관리자 화면. 상담사 앱(AppLayout)과 따로 그린다. 메뉴는 주소(/admin/accounts 등)로 나뉘어 새로고침해도 유지된다.
    // 관리자 확인 · 로그인 끊김 처리는 AdminApp 안(useAdminSession)에서 한다.
    path: "/admin/:view?",
    element: <AdminApp />,
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
      { path: "cases/:caseId/sessions/:sessionId/document", element: <DocumentWritePage /> },
      { path: "cases/:caseId/analyses", element: <AIAnalysisListPage /> },
      { path: "cases/:caseId/analyses/:analysisId", element: <AIReviewView /> },
      { path: "cases/:caseId/plan", element: <CasePlanView /> },
      { path: "cases/:caseId/closure", element: <ClosureView /> },
      { path: "cases/:caseId/reports", element: <ReportView /> },
      { path: "follow-up", element: <FollowUpPage /> },
      { path: "stt-cases", element: <STTCaseSelectorPage /> },
      { path: "case-management", element: <CaseManagementPage /> },
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
