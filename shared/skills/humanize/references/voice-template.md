# Voice profile — template

A voice profile describes how one person writes, so humanize can rewrite text in their voice. Use this file to build one for the user when they have none.

## Building a profile

1. Collect writing the person did themselves, unedited, for each register they write in: chat messages, design docs, MR or PR descriptions, review comments. Nothing an AI drafted or rewrote. A few dozen chat messages and two or three longer pieces are enough to measure.
2. Measure before describing: message and paragraph length, casing at the start of a line, closing punctuation, emoji per message, contractions and dropped apostrophes, bullet use and how bullets end, thousands separators. Write counts, not adjectives: "3 emoji in 50 messages", not "rarely uses emoji".
3. Write each rule from what the samples show, quoting a few words as evidence. Leave out any rule no sample supports.
4. Paste a few samples verbatim at the bottom, one or more per register. Swap out other people's names, private links, and anything the person would not want in the file.
5. Have the person read the profile and correct it.
6. Save it outside the humanize skill's folder, which an update replaces.

## Skeleton

Keep the headings. Add or drop register sections to match what the person writes, and drop any field the samples say nothing about.

````markdown
# <Name>'s voice profile

<Which registers this covers, and what the samples were drawn from.>

## Formatting — every register

- Bullets or paragraphs: <when the person uses each>
- Bullet style: <closing punctuation, bold labels or not, length, nesting>
- Group headings: <markdown headers, or a plain line ending in a colon>
- Numbers and units: <thousands separators, unit spacing>
- Spelling: <how the person spells team terms and product names>

## <Register> register — <where it is used>

- Openings and closings: <how a message or doc starts and ends>
- Sentences: <length, fragments, run-ons, comma splices, casing, closing punctuation>
- Person: <"I" or "we", and for what>
- Hedges: <the words used, and for what kind of uncertainty>
- Emphasis: <bold, a short flat sentence, nothing>
- Emoji, slang, typos: <measured rate, and where they appear>
- Length: <typical message or paragraph length>
- Rendering: <whether the destination renders markdown tables and mermaid diagrams>

## Lexicon

- Words and phrases the person reaches for: <list>
- Abbreviations: <list>
- Words the person never uses: <list>

## Boundaries

- <What the voice never does, even where the register would allow it>

## Samples (verbatim — the ground truth; where the profile and a sample disagree, trust the sample)

### <Register> (<source>)

> <verbatim text>
````
