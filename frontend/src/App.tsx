import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { LoginPage } from "@/features/auth/LoginPage";
import { SignupPage } from "@/features/auth/SignupPage";
import { CharactersPage } from "@/features/characters/CharactersPage";
import { StoriesListPage } from "@/features/stories/StoriesListPage";
import { StoryDetailPage } from "@/features/stories/StoryDetailPage";
import { WritingRoom } from "@/features/writing-room/WritingRoom";

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <StoriesListPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/characters"
        element={
          <ProtectedRoute>
            <CharactersPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/stories/:storyId"
        element={
          <ProtectedRoute>
            <StoryDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/stories/:storyId/chapters/:chapterId"
        element={
          <ProtectedRoute>
            <WritingRoom />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
