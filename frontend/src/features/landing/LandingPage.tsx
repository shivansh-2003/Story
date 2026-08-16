import { LandingNav } from "./LandingNav";
import { Hero } from "./Hero";
import { TheLoop } from "./TheLoop";
import { Pillars } from "./Pillars";
import { StoryBibleDemo } from "./StoryBibleDemo";
import { ClosingCTA } from "./ClosingCTA";
import { LandingFooter } from "./LandingFooter";

export function LandingPage() {
  return (
    <div>
      <LandingNav />
      <Hero />
      <TheLoop />
      <Pillars />
      <StoryBibleDemo />
      <ClosingCTA />
      <LandingFooter />
    </div>
  );
}
