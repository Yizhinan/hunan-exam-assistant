import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { BookOpen, LogOut, User } from "lucide-react";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <nav className="bg-white border-b border-gray-200 shadow-sm">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        <div
          className="flex items-center gap-2 cursor-pointer"
          onClick={() => navigate("/")}
        >
          <BookOpen className="h-5 w-5 text-primary-600" />
          <span className="font-semibold text-lg">湖南公考助手</span>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5 text-sm text-gray-600">
            <User className="h-4 w-4" />
            <span>{user?.display_name || user?.username}</span>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 transition-colors"
          >
            <LogOut className="h-4 w-4" />
            退出
          </button>
        </div>
      </div>
    </nav>
  );
}
