import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "./i18n";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Navbar from "./components/Navbar";

import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ProfilePage from "./pages/ProfilePage";
import DashboardPage from "./pages/DashboardPage";
import HomePage from "./pages/HomePage";

import RequestPage from "./pages/patient/RequestPage";
import AppointmentsPage from "./pages/patient/AppointmentsPage";
import DocumentsPage from "./pages/patient/DocumentsPage";
import RemindersPage from "./pages/patient/RemindersPage";
import InsurancePage from "./pages/patient/InsurancePage";
import BillingPage from "./pages/patient/BillingPage";

import WorkflowsPage from "./pages/staff/WorkflowsPage";
import ManagePage from "./pages/staff/ManagePage";
import EscalationsPage from "./pages/staff/EscalationsPage";
import AuditPage from "./pages/staff/AuditPage";

import "./index.css";

function ProtectedRoute({ children, allowedRole }: { children: React.ReactNode; allowedRole?: string }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (allowedRole && user.role !== allowedRole) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  const { loading } = useAuth();
  if (loading) return null;

  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />

      {/* Patient Portal */}
      <Route path="/request" element={<ProtectedRoute allowedRole="patient"><RequestPage /></ProtectedRoute>} />
      <Route path="/appointments" element={<ProtectedRoute allowedRole="patient"><AppointmentsPage /></ProtectedRoute>} />
      <Route path="/documents" element={<ProtectedRoute allowedRole="patient"><DocumentsPage /></ProtectedRoute>} />
      <Route path="/reminders" element={<ProtectedRoute allowedRole="patient"><RemindersPage /></ProtectedRoute>} />
      <Route path="/insurance" element={<ProtectedRoute allowedRole="patient"><InsurancePage /></ProtectedRoute>} />
      <Route path="/billing" element={<ProtectedRoute allowedRole="patient"><BillingPage /></ProtectedRoute>} />

      {/* Staff Console */}
      <Route path="/workflows" element={<ProtectedRoute allowedRole="staff"><WorkflowsPage /></ProtectedRoute>} />
      <Route path="/manage" element={<ProtectedRoute allowedRole="staff"><ManagePage /></ProtectedRoute>} />
      <Route path="/escalations" element={<ProtectedRoute allowedRole="staff"><EscalationsPage /></ProtectedRoute>} />
      <Route path="/audit" element={<ProtectedRoute allowedRole="staff"><AuditPage /></ProtectedRoute>} />
      <Route path="/dashboard" element={<ProtectedRoute allowedRole="staff"><DashboardPage /></ProtectedRoute>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Navbar />
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
