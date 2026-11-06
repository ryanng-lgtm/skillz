---
name: om-mrs
description: >-
  Use when the MRs a piece of work opened, with their links and merge order,
  have to go to OM Chat: as a draft for Ryan in #draft-replies, or posted in
  the topic where the work is discussed. Trigger: /om-mrs [topic link],
  $om-mrs [topic link], "post the MRs to om chat", "draft the MR list",
  "put the MRs and merge order in the topic".
---

# om-mrs — post a work's MRs and merge order to OM Chat in one fixed format

## Overview

Ryan's teammates read the same MR post in every topic, so it always has the
same shape: the MRs, then the order they merge in, every MR a link, and
nothing else.

**Core principle: the message is the template below, filled in. Anything the template has no slot for stays out.**

## Procedure

1. **Collect the MRs** this work opened, in every repo, from the session and
   its plan or brief. Read each one live with
   `glab mr view <iid> -R <group/project> -F json`: its `web_url`, state, and
   project path. The link is that `web_url`, or a link the session already
   has; never build one from a guessed path. The repo name is the project
   path's last segment.
2. **Work out the merge order** from dependencies, not from the order the
   work was done: a library before the code that pins it, a producer
   deployed before the consumer that reads its new field, a migration before
   the code that uses it. Use the session's merge order when it already has
   one, checked against the live state.
3. **Fill in the template**, in a file in this session's scratchpad (else
   `${TMPDIR:-/tmp}`):

   ```text
   MRs:
   - <repo>: [!<iid>](<web_url>)

   Merge order:
   1. [!<iid>](<web_url>) from <repo>
   2. [!<iid>](<web_url>) from <repo>, <before>, then <after>
   ```

   - One `MRs:` line per MR, in merge order. Two MRs in one repo are two lines.
   - One numbered step per MR. After `from <repo>` comes at most one clause
     of what must be true before it merges (`after …`, `only once …`) and
     what to do once it has (`then deploy to ore`), as short plain phrases.
     An MR nothing gates and that gates nothing ends `, any time`. A merged
     one ends `, already merged`.
   - Every MR named anywhere, inside a clause too, is `[!<iid>](<web_url>)`.
   - With one MR, the message is only the `MRs:` section.
   - When Ryan gave a line to lead with, it goes above `MRs:` as he wrote
     it, then a blank line.

   Example:

   ```text
   MRs:
   - auth-lib: [!41](https://gitlab.com/acme/auth-lib/-/merge_requests/41)
   - billing: [!118](https://gitlab.com/acme/billing/-/merge_requests/118)
   - docs: [!9](https://gitlab.com/acme/docs/-/merge_requests/9)

   Merge order:
   1. [!41](https://gitlab.com/acme/auth-lib/-/merge_requests/41) from auth-lib
   2. [!118](https://gitlab.com/acme/billing/-/merge_requests/118) from billing, after bumping its auth-lib pin to [!41](https://gitlab.com/acme/auth-lib/-/merge_requests/41)'s merge commit, then deploy to staging
   3. [!9](https://gitlab.com/acme/docs/-/merge_requests/9) from docs, any time
   ```

4. **Deliver it** with the om-chat skill's room tools, posting the file's
   text unchanged with `room_post`:
   - No argument: a draft, posted in `#draft-replies` (room `07f8a9476ba8`).
   - A topic link, or "the topic": in that topic (`room_post` with its room
     and `topicId`). Without a link, use the topic the work came from when
     the session has its link; otherwise ask Ryan which one.
5. **Read it back** with `room_message_get` and check its text matches the
   file. Report the room, the topic and the message link. A post the badge's
   posting policy turned into a draft is reported as staged, not posted.

## Rules

- **The humanize pass does not apply.** The template is the format; reflowing
  it is the instability this skill exists to stop.
- **Post only where Ryan asked.** Without a topic link or "topic", the message
  goes to `#draft-replies`, never to a channel.

## Common mistakes

- **Adding to the template**: an intro paragraph, a review request, a
  description per MR, the reason a step waits, bold, emoji. Each run adds
  different ones, which is the drift. Ryan adds his own words when he sends it.
- **Link text other than `!<iid>`**, or a bare `!<iid>` inside a clause.
- **Making a deploy its own numbered step.** It goes in the clause of the MR
  it follows, as `then deploy to …`.
