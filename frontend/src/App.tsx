import { Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./hooks/useAuth";
import AppLayout from "./components/layout/AppLayout";
import LoginPage from "./pages/Auth/LoginPage";
import RegisterPage from "./pages/Auth/RegisterPage";
import Home from "./pages/Home";
import SubmitPage from "./pages/EssayGrading/SubmitPage";
import ResultPage from "./pages/EssayGrading/ResultPage";
import HistoryPage from "./pages/EssayGrading/HistoryPage";
import TodayPage from "./pages/DailyEssay/TodayPage";
import ArchivePage from "./pages/DailyEssay/ArchivePage";
import AnalysisForm from "./pages/Analysis/FormPage";
import AnalysisResult from "./pages/Analysis/ResultPage";
import AdminDashboard from "./pages/Admin/Dashboard";

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route element={<AppLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/essay" element={<SubmitPage />} />
          <Route path="/essay/:essayId" element={<ResultPage />} />
          <Route path="/essay/history" element={<HistoryPage />} />
          <Route path="/daily" element={<TodayPage />} />
          <Route path="/daily/archive" element={<ArchivePage />} />
          <Route path="/daily/:essayId" element={<TodayPage />} />
          <Route path="/analysis" element={<AnalysisForm />} />
          <Route path="/analysis/result" element={<AnalysisResult />} />
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}

export default App;
