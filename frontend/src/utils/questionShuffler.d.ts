export interface RawQuestion {
  id: string | number;
  question: string;
  options: Array<string | { id: string; text: string }>;
  correctAnswer?: string;
  correct_option?: string;
  [key: string]: any;
}

export interface OptionItem {
  id: string;
  text: string;
}

export interface StudentSafeQuestion {
  id: string | number;
  displayIndex: number;
  question: string;
  options: string[];
  optionItems: OptionItem[];
  shuffledOrder: string[];
  [key: string]: any;
}

export function stringHashCode(str: string | number): number;
export function seededRandom(seed: number): () => number;
export function shuffleWithSeed<T>(array: T[], seedNumber: number): T[];
export function generateStudentPaper(rawQuestions: RawQuestion[], studentSeed: number | string): StudentSafeQuestion[];

