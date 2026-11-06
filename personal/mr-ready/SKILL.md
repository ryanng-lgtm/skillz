---
name: mr-ready
description: >-
  Use when the MRs a piece of work opened are ready and have to go to OM Chat
  with their links and merge order: as a draft for Ryan in #draft-replies, or
  posted in the topic where the work is discussed. Trigger: /mr-ready [topic
  link], $mr-ready [topic link], "post the MRs to om chat", "draft the MR
  list", "put the MRs and merge order in the topic".
---

# mr-ready — announce a work's MRs in OM Chat: what it fixes, the links, the merge order

## Overview

Ryan's teammates read the same MR post in every topic, so it always has the
same shape: a short TLDR, the MRs, then the order they merge in, every MR a
link, and nothing else.

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
3. **Write the TLDR**: two or three sentences, under 150 words, for someone
   who was not in the session, in this order:
   1. the problem, as the people who hit it saw it;
   2. what the change does about it, as behavior, not code;
   3. how it was shown to work: the checks the session ran or the MRs record
      (tests, a shared-dev probe, a prod read), each with its result. When
      only unit tests ran, say so.

   Then run the humanize skill in light mode on the TLDR alone, and count
   again: two or three sentences, under 150 words.
4. **Fill in the template**, in a file in this session's scratchpad (else
   `${TMPDIR:-/tmp}`):

   ```text
   TLDR:
   <the TLDR>

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
   - Every MR named in the lists, inside a clause too, is
     `[!<iid>](<web_url>)`.
   - With one MR, the message is the TLDR and the `MRs:` section.
   - When Ryan gave a line to lead with, it goes above `TLDR:` as he wrote
     it, then a blank line.

   Example:

   ```text
   TLDR:
   Anyone whose login had been refreshed in the last hour got sent back to the sign-in page when they opened billing. Billing now accepts refreshed logins, and the change in auth-lib that it needs ships first. On staging, a refreshed login opened billing without a redirect, and both repos' test suites pass.

   MRs:
   - auth-lib: [!41](https://gitlab.com/acme/auth-lib/-/merge_requests/41)
   - billing: [!118](https://gitlab.com/acme/billing/-/merge_requests/118)
   - docs: [!9](https://gitlab.com/acme/docs/-/merge_requests/9)

   Merge order:
   1. [!41](https://gitlab.com/acme/auth-lib/-/merge_requests/41) from auth-lib
   2. [!118](https://gitlab.com/acme/billing/-/merge_requests/118) from billing, after bumping its auth-lib pin to [!41](https://gitlab.com/acme/auth-lib/-/merge_requests/41)'s merge commit, then deploy to staging
   3. [!9](https://gitlab.com/acme/docs/-/merge_requests/9) from docs, any time
   ```

5. **Deliver it** with the om-chat skill's room tools, posting the file's
   text unchanged with `room_post`:
   - No argument: a draft, posted in `#draft-replies` (room `07f8a9476ba8`).
   - A topic link, or "the topic": in that topic (`room_post` with its room
     and `topicId`). Without a link, use the topic the work came from when
     the session has its link; otherwise ask Ryan which one.
6. **Read it back** with `room_message_get` and check its text matches the
   file. Report the room, the topic and the message link. A post the badge's
   posting policy turned into a draft is reported as staged, not posted.

## Rules

- **Only the TLDR goes through humanize**, in light mode. The labels and
  lists are the format; reflowing them is the drift this skill exists to stop.
- **Post only where Ryan asked.** Without a topic link or "topic", the message
  goes to `#draft-replies`, never to a channel.

## Common mistakes

- **Adding to the template**: an intro paragraph, a review request, a
  description per MR, the reason a step waits, bold, emoji. Each run adds
  different ones, which is the drift. Ryan adds his own words when he sends it.
- **A TLDR that retells the session**: what was suspected, tried and ruled
  out, or the files and functions changed. It is the problem, the fix and
  the proof, for a reader who was not there.
- **Link text other than `!<iid>`**, or a bare `!<iid>` inside a clause.
- **Making a deploy its own numbered step.** It goes in the clause of the MR
  it follows, as `then deploy to …`.
