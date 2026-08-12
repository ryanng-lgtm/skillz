---
name: openmarket-secrets
description: Send and open end-to-end sealed (encrypted) messages in OM Rooms with the secrets_send and secrets_open verbs. Use when a chat user asks you to send something privately/secretly to specific people, when someone hands YOU a credential sealed to your agent mailbox, or when you need to handle a secret value (API key, password, private note) that must not appear in plain chat.
user-invocable: false
---

# Sealed secrets — the agent playbook

Sealed secrets are end-to-end encrypted items that live in a room's timeline but
whose contents only the named recipients can read. The relay, other members, and
anyone reading history see a locked row: "sealed message · N recipients." The
plaintext is encrypted on the sender's daemon and decrypted only on a recipient's
daemon. You have two verbs and one hard rule.

## The one hard rule

**Never put a secret value into a normal post, a brief, a summary, a whisper, or
any tool call other than `secrets_send`.** If a value arrived through
`secrets_open`, or a human told you "this is a secret / a key / a password,"
it is sensitive: use it to do the task, then let it go. Do not echo it back,
quote it, or write it into a doc. A sealed value that you paste into a plain
message has been leaked to everyone in the room.

## secrets_send — send something privately

Use `secrets_send` when the operator asks you to send a value to specific people
so that only they can read it: an API key to a teammate, a private note to one
person in a busy room, an address or credential.

- `room` — the room to post the sealed item into.
- `message` — the plaintext. It is encrypted before it leaves the daemon.
- `recipients` — the userIds who may open it. They MUST be current members of
  that room (or the operator). You cannot seal to someone outside the room, and
  you cannot seal to an arbitrary account. Omit `recipients` to seal to every
  member of the room who has a mailbox.

If some recipients have no mailbox yet, the verb tells you (`skippedNoCard`):
those people simply can't receive sealed items until they've used secrets once.
Report that to the operator rather than sending the value in the clear instead.

`secrets_send` is only available to you in armed mode, and only when the operator
has explicitly granted it. In a normal (lane) turn you cannot seal-and-send:
instead, tell the operator what you'd send and let them use the composer's seal
toggle. That is by design — sealing on the operator's behalf is their call.

## secrets_open — read something sealed TO YOU

A human can hand you a credential safely by sealing it to your **agent mailbox**.
When that happens you'll see a sealed row addressed to you. Use `secrets_open`
with that entry's `secret` payload to read it.

- You can ONLY open messages sealed to your own agent mailbox. Messages sealed to
  the operator or to other people are not openable by you — there is no verb for
  it, and the encryption itself prevents it. This is a wall, not a setting.
- The opened value is marked sensitive. Use it for the immediate task (call the
  API, run the check) and never repeat it in chat.

## When NOT to seal

Ordinary conversation stays ordinary — do not seal normal chatter. Sealing is for
values that would cause harm if the whole room could read them. When unsure
whether something is sensitive, ask the operator rather than guessing.
