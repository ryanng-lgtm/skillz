# Ryan's voice profile

Built from real samples (bottom of file). Two registers covered; MR descriptions use the doc register, tighter. Commit messages are out of scope (repo format governs them).

## Doc register — design docs, READMEs, MR descriptions

- First person singular for decisions, with the why: "I deliberately left the default policy alone. If you change group_by on the default it affects every alert in the org…"
- First person plural for team intent: "We want a way to…", "We've opted to use…"
- Hedges tied to knowledge source: "From what I've read it's basically…", "Assuming it lives in the occ cluster…"
- "basically", "The idea is to…", "The only thing that matters here is…"
- Long conditional chains joined with "and", ending in a plain judgement: "…which is not what we want."
- Comma splices tolerated: "Any other alerts with the same label get fired, it will coalesce into a deduped notif stream"
- Abbreviations mid-prose: "notif"
- Concrete numeric examples: "10 rules firing at once will still only produce one webhook call"
- Flat consequence statements: "Without this step we could create incidents but never close them."
- Emphasis via short plain sentence, not adverbs: "This is also what makes resolve work at all."
- "X is the one that…" constructions: "Grafana is the one that creates the identity, and the bridge is the one that makes it survive"
- Playful naming acknowledged in quotes: "that's where the bridge service would come in, to 'bridge' the gap"
- Plain headers: Overview, Context/Problem, Goals and Non-goals, Proposed Design
- Occasionally drops the trailing period on a block's last line
- Casual dismissals in scoping: "we assume whatever is configured there is sufficient"

## Chat register — Discord/Slack

- Starts mid-thought, no greeting or setup: "Best example I can give was with replay feature"
- Typos stay: "tht", articles dropped: "with replay feature"
- Abbreviations: "ntg" (nothing), "picked to prod" (cherry-picked)
- Slang and profanity casual: "tht shit went on for almost two weeks", "it was cooked", "for the homies"
- People as lowercase initials: "kw"
- Long run-ons chained with "but/and", no terminal punctuation
- **No emoji.** Zero in samples.
- Does NOT summarize everything — tells the one story/point that matters

## Raw samples (verbatim — the ground truth; when profile and sample disagree, trust the sample)

Imitate the patterns, never the sentences. When the target overlaps a sample's subject matter, copying sample sentences wholesale is plagiarism of the profile, not voice — write fresh sentences in the same shapes.

### Doc (statuspage bridge design doc, excerpt)

> We route these through a nested notification policy that matches on statuspage_component =~ ".+" and overrides the grouping to just that one label. I deliberately left the default policy alone. If you change group_by on the default it affects every alert in the org, and if alertname stays in the grouping you end up with one incident per rule instead of one per component, which is not what we want.
>
> When the notification goes out, Grafana's embedded Alertmanager attaches a groupKey to it (assuming we use Grafana managed alerts). From what I've read it's basically a string built from the route and the grouping label values, so something like {}/{statuspage_component=~".+"}:{statuspage_component="website"} (ref). It's Grafana's way to ensure the same group always produces the same key.
>
> The bridge hashes that groupKey (sha256, first 12 chars) and writes the hash into the incident's metadata when it creates it. So Grafana is the one that creates the identity, and the bridge is the one that makes it survive by attaching it to the incident itself
>
> Any other alerts with the same label get fired, it will coalesce into a deduped notif stream, and this prevents spamming incidents since 10 rules firing at once will still only produce one webhook call.
>
> This is also what makes resolve work at all. The resolved notification comes in with the same groupKey, the bridge hashes it again, finds the open incident whose metadata has that hash, and closes that one specifically. Without this step we could create incidents but never close them.

### Chat (Discord)

> Best example I can give was with replay feature, tht shit went on for almost two weeks, with multiple fixes and commits into main but ntg on prod and at the end it was cooked when kw tried to merge it to prod
>
> but replay only had a single entry point and I could've gated it from there and still picked to prod early for the homies who want faster queries without the bloat
