import type { Claim, HumanReview, ReviewResponseBody } from "@/lib/types";

export interface ReviewFormProps {
  review: HumanReview;
  claims: readonly Claim[];
  /** Whether the current persona holds the review's required role. */
  canAct: boolean;
  onSubmit: (body: ReviewResponseBody) => Promise<void>;
}
