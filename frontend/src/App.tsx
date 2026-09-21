import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import Footer from "./components/Footer";
import Navigation from "./components/Navigation";
import RequireRole from "./components/RequireRole";
import { AuthProvider } from "./context/AuthContext";
import AnalyzePage from "./pages/AnalyzePage";
import CasePage from "./pages/CasePage";
import CasesPage from "./pages/CasesPage";
import FileComplaintPage from "./pages/FileComplaintPage";
import LoginPage from "./pages/LoginPage";
import MyComplaintsPage from "./pages/MyComplaintsPage";
import StaffPage from "./pages/StaffPage";

export default function App() {
  return (
    <HashRouter>
      <AuthProvider>
        <div className="min-h-screen bg-vellum flex flex-col">
          <Navigation />
          <main className="flex-1">
            <Routes>
              <Route path="/login" element={<LoginPage />} />

              {/* Police staff */}
              <Route
                path="/cases"
                element={
                  <RequireRole roles={["officer", "admin"]}>
                    <CasesPage />
                  </RequireRole>
                }
              />
              <Route
                path="/cases/:id"
                element={
                  <RequireRole roles={["officer", "admin"]}>
                    <CasePage />
                  </RequireRole>
                }
              />
              <Route
                path="/new"
                element={
                  <RequireRole roles={["officer", "admin"]}>
                    <AnalyzePage />
                  </RequireRole>
                }
              />
              <Route
                path="/staff"
                element={
                  <RequireRole roles={["admin"]}>
                    <StaffPage />
                  </RequireRole>
                }
              />
              <Route path="/history" element={<Navigate to="/cases" replace />} />

              {/* Citizens */}
              <Route
                path="/file"
                element={
                  <RequireRole roles={["citizen"]}>
                    <FileComplaintPage />
                  </RequireRole>
                }
              />
              <Route
                path="/my-complaints"
                element={
                  <RequireRole roles={["citizen"]}>
                    <MyComplaintsPage />
                  </RequireRole>
                }
              />

              <Route path="/" element={<Navigate to="/cases" replace />} />
              <Route path="*" element={<Navigate to="/cases" replace />} />
            </Routes>
          </main>
          <Footer />
        </div>
      </AuthProvider>
    </HashRouter>
  );
}
