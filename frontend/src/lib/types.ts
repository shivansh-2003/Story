export type UUID = string;

export type User = {
  id: UUID;
  email: string;
  created_at: string;
};

export type Character = {
  id: UUID;
  user_id: UUID;
  name: string;
  role: string | null;
  age: string | null;
  pronouns: string | null;
  appearance: string | null;
  voice_notes: string | null;
  personality_traits: string[] | null;
  motivation: string | null;
  flaw: string | null;
  backstory: string | null;
  condensed_summary: string | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
};

export type CharacterRelationship = {
  id: UUID;
  character_id: UUID;
  related_character_id: UUID;
  relationship_label: string | null;
};

export type POV = "first_person" | "third_limited" | "third_omniscient";
export type Tense = "past" | "present";
export type StoryStatus = "draft" | "ongoing" | "on_hold" | "completed" | "abandoned";
export type ChapterStatus = "draft" | "in_progress" | "in_review" | "complete" | "locked";

export type Story = {
  id: UUID;
  user_id: UUID;
  title: string;
  genre: string[] | null;
  tone: string | null;
  pov: POV | null;
  tense: Tense | null;
  rating: string | null;
  premise: string | null;
  opening_line: string | null;
  setting: string | null;
  themes: string[] | null;
  content_boundaries: string | null;
  writing_style_notes: string | null;
  target_audience: string | null;
  status: StoryStatus;
  created_at: string;
  updated_at: string;
};

export type StoryDetail = Story & {
  characters: Character[];
};

export type Chapter = {
  id: UUID;
  story_id: UUID;
  order_index: number;
  title: string | null;
  status: ChapterStatus;
  summary: string | null;
  target_length_words: number | null;
  created_at: string;
  updated_at: string;
};

export type ChapterDetail = Chapter & {
  body: string;
};

export type Turn = {
  content: string;
  instruction: string | null;
  source: "ai" | "user_edit";
};
