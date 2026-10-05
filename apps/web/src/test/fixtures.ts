import awaitingDecision from "../../fixtures/investigation-awaiting-decision.json";
import claimChain from "../../fixtures/claim-chain.json";
import decided from "../../fixtures/investigation-decided.json";
import privacyReview from "../../fixtures/investigation-privacy-review.json";
import type { ClaimChain, InvestigationDetail } from "@/lib/types";

// JSON imports widen enums to `string`; these are real API responses, so the cast is sound.
export const awaitingDecisionFixture = awaitingDecision as unknown as InvestigationDetail;
export const decidedFixture = decided as unknown as InvestigationDetail;
export const privacyReviewFixture = privacyReview as unknown as InvestigationDetail;
export const claimChainFixture = claimChain as unknown as ClaimChain;
