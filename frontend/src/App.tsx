import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageTransition } from "@/components/PageTransition";
import { AppShell } from "@/components/shells/AppShell";
import { GalleyShell } from "@/components/shells/GalleyShell";
import { Toaster } from "@/components/ui/sonner";
import { Skeleton } from "@/components/ui/skeleton";
import { LoginPage } from "@/features/auth/LoginPage";
import { SignupPage } from "@/features/auth/SignupPage";

// Every page below except login/signup is its own lazy chunk — login/signup
// stay in the main bundle since they're the likely first stop for a
// signed-out visitor and are small on their own. Splitting the rest keeps
// three.js, Motion's Reorder, and the galley's animation code out of that
// first-paint bundle. See the design spec's per-route JS budgets (§16).
const LandingPage = lazy(() => import("@/features/landing/LandingPage").then((m) => ({ default: m.LandingPage })));
const CastPage = lazy(() => import("@/features/characters/CastPage").then((m) => ({ default: m.CastPage })));
const StoryLibraryPage = lazy(() =>
  import("@/features/stories/StoryLibraryPage").then((m) => ({ default: m.StoryLibraryPage })),
);
const StoryLayout = lazy(() => import("@/features/stories/StoryLayout").then((m) => ({ default: m.StoryLayout })));
const BibleTab = lazy(() => import("@/features/stories/BibleTab").then((m) => ({ default: m.BibleTab })));
const StoryCastTab = lazy(() => import("@/features/stories/StoryCastTab").then((m) => ({ default: m.StoryCastTab })));
const ChapterListPage = lazy(() =>
  import("@/features/chapters/ChapterListPage").then((m) => ({ default: m.ChapterListPage })),
);
const GalleyPage = lazy(() => import("@/features/galley/GalleyPage").then((m) => ({ default: m.GalleyPage })));

function PageSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}

// "/" always renders the public landing page, signed in or not — the
// AppShell wordmark links here, and it needs to actually land you on it
// rather than bounce you straight back to /library. Its own CTAs ("Start
// writing", "Sign in") already redirect a signed-in visitor onward once
// they act on them, via LoginPage/SignupPage's own signed-in redirect.
function Root() {
  return (
    <Suspense fallback={null}>
      <LandingPage />
    </Suspense>
  );
}

function App() {
  return (
    <>
      <Toaster />
      <PageTransition>
        <Routes>
          <Route path="/" element={<Root />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route
            path="/library"
            element={
              <ProtectedRoute>
                <AppShell>
                  <Suspense fallback={<PageSkeleton />}>
                    <StoryLibraryPage />
                  </Suspense>
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/cast"
            element={
              <ProtectedRoute>
                <AppShell>
                  <Suspense fallback={<PageSkeleton />}>
                    <CastPage />
                  </Suspense>
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/stories/:storyId"
            element={
              <ProtectedRoute>
                <AppShell>
                  <Suspense fallback={<PageSkeleton />}>
                    <StoryLayout />
                  </Suspense>
                </AppShell>
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="chapters" replace />} />
            <Route
              path="chapters"
              element={
                <Suspense fallback={<PageSkeleton />}>
                  <ChapterListPage />
                </Suspense>
              }
            />
            <Route
              path="cast"
              element={
                <Suspense fallback={<PageSkeleton />}>
                  <StoryCastTab />
                </Suspense>
              }
            />
            <Route
              path="bible"
              element={
                <Suspense fallback={<PageSkeleton />}>
                  <BibleTab />
                </Suspense>
              }
            />
          </Route>
          <Route
            path="/stories/:storyId/chapters/:chapterId"
            element={
              <ProtectedRoute>
                <GalleyShell>
                  <Suspense fallback={<PageSkeleton />}>
                    <GalleyPage />
                  </Suspense>
                </GalleyShell>
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/library" replace />} />
        </Routes>
      </PageTransition>
    </>
  );
}

export default App;
