import { request } from "../../shared/api/client";
import type { JudgeAssessment, JudgeAgreement, Review, ReviewAgreement } from "./types";

export const reviewsApi = {
  create: (body: Record<string, unknown>) => request<Review>("/reviews", { method: "POST", body: JSON.stringify(body) }),
  list: (attemptId: string) => request<Review[]>(`/reviews/sample/${attemptId}`),
  agreement: (attemptId: string) => request<ReviewAgreement>(`/reviews/sample/${attemptId}/agreement`),
  createJudge: (body: Record<string, unknown>) => request<JudgeAssessment>("/judge-assessments", { method: "POST", body: JSON.stringify(body) }),
  createJudgeComparison: (body: Record<string, unknown>) => request<JudgeAssessment[]>("/judge-assessments/compare", { method: "POST", body: JSON.stringify(body) }),
  listJudges: (attemptId: string) => request<JudgeAssessment[]>(`/judge-assessments/sample/${attemptId}`),
  judgeAgreement: (attemptId: string) => request<JudgeAgreement>(`/judge-assessments/sample/${attemptId}/agreement`),
};

export type { JudgeAssessment, JudgeAgreement, Review, ReviewAgreement } from "./types";
