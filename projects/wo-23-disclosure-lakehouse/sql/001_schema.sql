CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE TABLE IF NOT EXISTS disclosure_fact (
  fact_id bigserial PRIMARY KEY,
  corp_code text NOT NULL,
  report_year integer NOT NULL,
  report_code text NOT NULL,
  concept text NOT NULL,
  context_key text NOT NULL,
  unit text NOT NULL DEFAULT '',
  value numeric,
  value_text text,
  valid_during daterange NOT NULL,
  is_current boolean NOT NULL DEFAULT true,
  receipt_no text NOT NULL,
  source_sha256 text NOT NULL,
  loaded_at timestamptz NOT NULL DEFAULT now(),
  CHECK (NOT isempty(valid_during)),
  CHECK ((value IS NULL) OR (value_text IS NULL)),
  UNIQUE (corp_code, report_year, report_code, concept, context_key, unit, receipt_no)
);
CREATE INDEX IF NOT EXISTS disclosure_fact_pit_gist
  ON disclosure_fact USING gist (corp_code, report_year, report_code, concept, context_key, unit, valid_during);
CREATE INDEX IF NOT EXISTS disclosure_fact_current_idx
  ON disclosure_fact (corp_code, report_year, report_code, concept, context_key, unit)
  WHERE is_current;
CREATE INDEX IF NOT EXISTS disclosure_fact_receipt_idx ON disclosure_fact (receipt_no);
