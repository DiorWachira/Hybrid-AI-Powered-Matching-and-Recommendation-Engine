import { Check, CircleAlert, EyeOff, Minus, Scale } from "lucide-react";
import type { EligibilityRequirement, MatchCandidate, ScoringModel } from "../lib/api";
import { COMBINER_NOTE, INPUTS, INPUT_ORDER, NOT_USED, RULES, RULE_ORDER, SCENARIOS, exclusionsByRule, explainScore, ruleOf, scenarioOf, type BiasNote, type RuleKey } from "../lib/decisionGuide";

const percent = (value: number) => `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`;
const signed = (value: number) => `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(2)}`;

function Bias({ note, label = "Where bias could enter" }: { note: BiasNote; label?: string }) {
  return <dl className="bias-note" aria-label={label}>
    <div><dt>Bias risk</dt><dd>{note.risk}</dd></div>
    <div><dt>How it was avoided</dt><dd>{note.guard}</dd></div>
  </dl>;
}

/**
 * After an evaluation: the steps that produced this candidate's result, with the bias risk at each step and what the
 * system does about it. Shown under the individual breakdown on the match analysis page.
 */
export function DecisionWalkthrough({ candidate, model, requirements, name }: { candidate: MatchCandidate; model: ScoringModel | null | undefined; requirements: EligibilityRequirement[] | null | undefined; name: string }) {
  const scenario = scenarioOf(candidate);
  const story = SCENARIOS[scenario];
  const failed = new Set(candidate.rule_reasons.map(ruleOf).filter((key): key is RuleKey => key !== null));
  const sameModel = !!model && candidate.model_version === model.version;
  const score = sameModel && candidate.hard_rule_passed ? explainScore(candidate, model) : null;
  const widest = score ? Math.max(1, ...score.contributions.map((item) => Math.abs(item.push))) : 1;
  const rules = requirements ?? RULE_ORDER.filter((key) => failed.has(key)).map((rule) => ({ rule, applied: true, requirement: null }));

  return <section className="decision-walkthrough" aria-labelledby="walkthrough-title">
    <header>
      <p className="eyebrow">How this decision was reached</p>
      <h3 id="walkthrough-title"><span className={`decision-verdict is-${scenario}`}>{story.title}</span></h3>
      <p>{story.decision}</p>
    </header>

    <div className="decision-summary">
      <div><h4>Bias to watch</h4><p>{story.watch}</p></div>
      <div><h4>How it was avoided</h4><p>{story.avoid}</p></div>
      <div><h4>What to do next</h4><p>{story.next}</p></div>
    </div>

    <ol className="decision-steps">
      <li>
        <h4><span>01</span>Eligibility rules</h4>
        <p>Every candidate is checked against the same rules from this posting before any score is calculated. A failed rule stops here.</p>
        {requirements === null || requirements === undefined ? <p className="decision-muted">This evaluation was saved before the posting's rules were recorded with it. Evaluate again to see each rule.</p> : null}
        <ul className="rule-checks">{rules.map((item) => {
          const outcome = failed.has(item.rule) ? "fail" : item.applied ? "pass" : "off";
          return <li key={item.rule} className={`is-${outcome}`}>
            {outcome === "fail" ? <CircleAlert size={15} aria-hidden="true" /> : outcome === "pass" ? <Check size={15} aria-hidden="true" /> : <Minus size={15} aria-hidden="true" />}
            <div>
              <strong>{RULES[item.rule].name}</strong>
              <small>{outcome === "off" ? "Not set on this posting, so not applied" : `${item.requirement ?? RULES[item.rule].checks} · ${outcome === "fail" ? "Not met" : "Met"}`}</small>
              {outcome === "fail" && <Bias note={RULES[item.rule].bias} label={`Bias in the ${RULES[item.rule].name} rule`} />}
            </div>
          </li>;
        })}</ul>
        {rules.some((item) => item.applied && !failed.has(item.rule)) && <details className="decision-more"><summary>Where bias could enter through the rules this candidate met</summary>
          {rules.filter((item) => item.applied && !failed.has(item.rule)).map((item) => <div key={item.rule}><h5>{RULES[item.rule].name}</h5><Bias note={RULES[item.rule].bias} label={`Bias in the ${RULES[item.rule].name} rule`} /></div>)}
        </details>}
      </li>

      <li>
        <h4><span>02</span>What the model read</h4>
        {candidate.hard_rule_passed ? <>
          <p>Three numbers, each from 0 to 100%. Nothing else about {name} reaches the model.</p>
          <ul className="input-reads">{INPUT_ORDER.map((key) => <li key={key}>
            <div><strong>{INPUTS[key].name}</strong><b>{percent(candidate[key])}</b></div>
            <small>{INPUTS[key].measures}</small>
            <details className="decision-more"><summary>Bias in this input</summary><Bias note={INPUTS[key].bias} label={`Bias in ${INPUTS[key].name}`} /></details>
          </li>)}</ul>
          <div className="never-seen"><h5><EyeOff size={15} aria-hidden="true" />Never given to the model</h5><ul>{NOT_USED.map((item) => <li key={item}>{item}</li>)}</ul></div>
        </> : <p className="decision-muted">Skipped. No score was calculated, so the language model, the skill graph and the trained weights played no part in this result.</p>}
      </li>

      <li>
        <h4><span>03</span>Combining the scores</h4>
        {score && model ? <>
          <p>Each input is compared with the average training candidate, then weighted. Above average pushes the score up; below average pulls it down. The same weights apply to everyone.</p>
          <table className="push-table">
            <thead><tr><th scope="col">Input</th><th scope="col">{name}</th><th scope="col">Average</th><th scope="col">Effect</th></tr></thead>
            <tbody>{score.contributions.map((item) => <tr key={item.key}>
              <th scope="row">{INPUTS[item.key].name}</th>
              <td>{percent(item.value)}</td>
              <td>{percent(item.average)}</td>
              <td><div className="push-cell"><span className="push-bar" aria-hidden="true"><i className={item.push >= 0 ? "up" : "down"} style={{ width: `${Math.abs(item.push) / widest * 50}%` }} /></span><span>{signed(item.push)} {item.push >= 0 ? "raised" : "lowered"}</span></div></td>
            </tr>)}</tbody>
          </table>
          <p className="push-sum">Starting point {model.intercept.toFixed(2)} {score.contributions.map((item) => signed(item.push)).join(" ")} = {score.logit.toFixed(2)}, which converts to a match score of <strong>{percent(candidate.final_score)}</strong>. The threshold is {percent(model.threshold)}, so this is {candidate.final_score >= model.threshold ? "at or above it: recommended" : "below it: not recommended"}.</p>
          <Bias note={COMBINER_NOTE} label="Bias in the trained model" />
        </> : <p className="decision-muted">{candidate.hard_rule_passed ? "This result came from an earlier model, so its weights are not shown. Evaluate again to see the calculation." : "Skipped, because the candidate did not meet the eligibility rules."}</p>}
      </li>

      <li>
        <h4><span>04</span>Your decision</h4>
        <p>The system recommends; you decide. Moving forward anyone it did not recommend shows a warning and is recorded with the score and rule result. A candidate who failed a rule needs a written reason, which the administrator can review.</p>
      </li>
    </ol>
  </section>;
}

/** Evaluation-wide checks: the same rules and model for everyone, and how many people each rule removed. */
export function FairnessPanel({ candidates, model, requirements }: { candidates: MatchCandidate[]; model: ScoringModel | null | undefined; requirements: EligibilityRequirement[] | null | undefined }) {
  if (!candidates.length) return null;
  const excluded = exclusionsByRule(candidates);
  const total = candidates.length;
  const applied = requirements ? requirements.filter((item) => item.applied) : RULE_ORDER.filter((key) => excluded[key] > 0).map((rule) => ({ rule, applied: true, requirement: null }));
  const largest = applied.reduce<RuleKey | null>((best, item) => excluded[item.rule] > (best ? excluded[best] : 0) ? item.rule : best, null);
  const versions = new Set(candidates.map((item) => item.model_version));
  return <details className="fairness-panel" open>
    <summary><Scale size={17} aria-hidden="true" /><span>Fairness check for this evaluation</span><small>{largest ? `${RULES[largest].name} removed ${excluded[largest]} of ${total}` : "No candidate was removed by a rule"}</small></summary>
    <div className="fairness-body">
      <section>
        <h3>Same process for everyone</h3>
        <ul className="fairness-facts">
          <li>{total} candidates checked against the same {applied.length} {applied.length === 1 ? "rule" : "rules"} from this posting.</li>
          <li>{versions.size === 1 && model && candidates[0].model_version === model.version ? `All scored by one model (${model.version}) with one threshold, ${percent(model.threshold)}.` : "Some results came from an earlier model. Evaluate again so everyone is scored the same way."}</li>
          <li>Equal scores are ordered by a random ID, never by name or sign-up order.</li>
          <li>Turn on blind review in the list below to hide names and locations while you shortlist.</li>
        </ul>
      </section>
      <section>
        <h3>Who each rule removed</h3>
        <p>Rules remove people before any score is calculated. Check that each one reflects a real need of the job.</p>
        {applied.length ? <ul className="exclusion-bars">{applied.map((item) => <li key={item.rule} className={item.rule === largest ? "is-largest" : ""}>
          <div><strong>{RULES[item.rule].name}</strong>{item.requirement && <small>{item.requirement}</small>}</div>
          <span className="exclusion-track" aria-hidden="true"><i style={{ width: `${excluded[item.rule] / total * 100}%` }} /></span>
          <b>{excluded[item.rule]} of {total}</b>
        </li>)}</ul> : <p className="decision-muted">No rules are set on this posting.</p>}
        <small className="decision-muted">A candidate can fail more than one rule, so the counts can add up to more than those removed.</small>
      </section>
      <section>
        <h3>Never given to the model</h3>
        <ul className="fairness-facts">{NOT_USED.map((item) => <li key={item}>{item}</li>)}</ul>
        <p className="decision-muted">Removal from CV text is best effort. The model has not been checked for fairness across groups, because the platform does not collect group data and the model is tested only on synthetic data.</p>
      </section>
    </div>
  </details>;
}
