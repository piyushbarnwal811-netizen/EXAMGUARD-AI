/**
 * ExamGuard AI - Deterministic Question & Option Shuffler
 * Module 2: Seeded PRNG & Fisher-Yates Implementation
 */

/**
 * Standard 32-bit unsigned string hash code (Java String.hashCode equivalent)
 */
export function stringHashCode(str) {
  let hash = 0;
  const s = String(str);
  for (let i = 0; i < s.length; i++) {
    hash = ((hash << 5) - hash) + s.charCodeAt(i);
    hash |= 0; // Convert to 32bit integer
  }
  return Math.abs(hash);
}

/**
 * Seeded PRNG (Mulberry32)
 */
export function seededRandom(seed) {
  let s = Number(seed) >>> 0;
  return function () {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t ^= t + Math.imul(t ^ (t >>> 7), 61 | t);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Deterministic Fisher-Yates Shuffle
 */
export function shuffleWithSeed(array, seedNumber) {
  const shuffled = [...array];
  const random = seededRandom(seedNumber);
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

/**
 * API Output Formatter for Candidate
 * Produces a reproducible, unique paper for each student without exposing the answer key.
 */
export function generateStudentPaper(rawQuestions, studentSeed) {
  const seedNum = typeof studentSeed === "string" ? stringHashCode(studentSeed) : Number(studentSeed) >>> 0;

  // 1. Shuffle Questions Sequence
  const shuffledQuestions = shuffleWithSeed(rawQuestions, seedNum);

  // 2. Shuffle Options for each question
  return shuffledQuestions.map((q, idx) => {
    const qId = q.id || idx + 1;
    const optionSeed = (seedNum + stringHashCode(String(qId)) + idx) >>> 0;

    // Normalizing options to object array
    const rawOptions = Array.isArray(q.options)
      ? q.options.map((opt, oIdx) =>
          typeof opt === "string"
            ? { id: String.fromCharCode(65 + oIdx), text: opt }
            : { id: opt.id || String.fromCharCode(65 + oIdx), text: opt.text || "" }
        )
      : [];

    const shuffledOptions = shuffleWithSeed(rawOptions, optionSeed);

    // Omit correctAnswer from the payload sent to student
    const { correctAnswer, correct_option, ...safeQuestion } = q;

    return {
      ...safeQuestion,
      id: qId,
      displayIndex: idx + 1,
      options: shuffledOptions.map((opt) => opt.text),
      optionItems: shuffledOptions, // [{ id: 'opt_B', text: '...' }]
      shuffledOrder: shuffledOptions.map((opt) => opt.id),
    };
  });
}

