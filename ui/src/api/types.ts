// Apelidos dos tipos gerados de contracts/openapi.yaml (npm run gen). Não edite schema.d.ts.
import type { components } from "./schema";

type S = components["schemas"];
export type Finding = S["finding.schema"];
export type Analysis = S["analysis.schema"];
export type Page = S["page.schema"];
export type QaDocument = S["document.schema"];
export type BatchStatus = S["batch-status.schema"];
export type Summary = S["batch-summary.schema"];
export type MetadataField = S["metadata-field.schema"];
export type Profile = S["profile.schema"];
export type Numbering = S["numbering.schema"];
export type Region = S["region.schema"];
export type DecisionRequest = S["decision-request.schema"];
export type DecisionAction = DecisionRequest["action"];
export type Severity = Finding["severity"];

export interface DecisionResponse {
  finding: Finding;
  summary: Summary;
  applied?: { output: string; output_sha256: string; remaining_rules: string[] };
}

export interface NumberingResponse {
  pages: Record<string, Numbering>;
  summary: Summary;
}
