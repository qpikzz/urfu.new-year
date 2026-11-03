# PRODUCT

Product definition of Urfu27bot (UrFU New Year). Describes what the bot does and for whom. Data schema, flows, message texts and infrastructure are defined in other specs.

## 1. Purpose

Urfu27bot is a Telegram bot for a New Year event: it organizes video greetings between participants connected to UrFU and builds a community around the event.

Core idea: a participant sends one video circle (Telegram video note) with a greeting and receives circles from other participants in return.

## 2. Audience and statuses

Every participant chooses one status:

| Status | Description |
|---|---|
| Applicant | School student applying to a university |
| UrFU student | Student of UrFU |
| Other university student | Student of another university |
| Student's parent | Parent of a student |
| University employee | Employee of any university (teachers, dean's office, etc.) |
| Other | Anyone else |

- The institute is collected for students and for university employees.
- Institute-level greetings (see section 8) apply to UrFU students only.
- Stricter automatic moderation applies to the statuses Applicant, Other university student and Other. It matters mainly for later development stages and has little effect on the MVP.

## 3. Participant lifecycle

1. Registration: the bot saves the Telegram data automatically.
2. The bot asks for the status.
3. The bot asks for the institute (students and employees only).
4. The bot asks for the time zone, expressed as an offset from UTC.
5. The participant sends one circle.
6. Automatic moderation.
7. Manual moderation.
8. The circle is approved or rejected.
9. After registration closes, triples are formed (section 7).
10. Delivery on 1 January at 00:00 local time of each participant (section 8).

## 4. Moderation

### 4.1. Automatic moderation

- Early stage: the audio track is extracted, converted to text and checked for forbidden words.
- Later stage: several frames of the video are checked for prohibited content (NSFW and similar).
- Speech recognition uses a simple own algorithm running on CPU. An external API is connected only under high load, when the queue exceeds 50 participants; part of the queue is then moved to the API. If the load is high and the API does not respond, the queue is processed locally, and automatic checking may take up to a week.

### 4.2. Manual moderation

- The bot sends the circle to the administrators' chat with the buttons ✅ and ❌.
- Administrators are defined by their ids in the environment configuration.
- ✅ approves the circle manually.
- ❌ offers four options: "Cancel, accept", "Contains profanity", "Contains shocking content", "Other reason".

### 4.3. Circle states

- 0: awaiting automatic moderation.
- 1: approved automatically.
- 2: approved manually.

Rejected circles are tracked separately in the data spec.

## 5. Limits and ban

- A participant has 3 attempts for automatic moderation.
- After a rejection, the participant may send exactly one more circle.
- After a rejection the participant sees the reason and a warning about the remaining limits.
- A participant who exhausts the limits is banned; messages from a banned participant are ignored.
- The attempt counters and limits are stored in the database.

## 6. Time windows

- Registration opens automatically when the bot is launched.
- Closing starts at 00:00 Yekaterinburg time on 25 December 2026. From then on, new circles cannot be sent.
- After closing, administrators finish moderating the remaining circles.
- The number of approved circles must be a multiple of 3. Surplus circles that remain are rejected with the reason "Other reason". The rule for selecting the surplus is defined in the flows spec.

## 7. Triples

Triples are formed once, after registration is closed and the last circles are moderated, and before delivery.

Algorithm:

1. Export all data of participants with approved circles.
2. Shuffle the list of participants randomly.
3. Split the shuffled list into 3 equal parts (columns).
4. Merge the columns side by side: each resulting row contains 3 HIDs and is one triple.

Example: a list of 12 participants becomes 3 columns of 4, which gives 4 rows (triples).

Properties:

- Every participant belongs to exactly one triple.
- Each participant receives the circles of the other two members of the triple, so pairs never repeat.
- The number of participants must be a multiple of 3.

## 8. Delivery plans

A participant receives content only if the participant's own circle is approved. Participants whose circles are rejected, who are banned, or who sent no circle receive nothing.

| Plan | Content | Audience |
|---|---|---|
| Minimum | 2 circles from the other members of the triple | All participants |
| Medium | Greeting from representatives of the participant's institute | UrFU students |
| Maximum | Greetings from the UrFU rector, the governor of the Sverdlovsk region and the President of Russia | All participants |

- Greetings of the medium and maximum plans are video files uploaded manually by an administrator.
- Delivery happens when the local time of the participant is 00:00 on 1 January, based on the stored time zone.
- Before the real delivery, test deliveries are run on a separate test bot.

## 9. MVP scope

Deadline: 20 November 2026.

Included:

- Registration, status, institute and time zone collection.
- Circle submission.
- Automatic moderation of the voice track.
- Manual moderation with approval and rejection.
- Attempt limits and ban.
- Delivery plan: Minimum only.

Triple formation and delivery are not part of the MVP deadline; they are tested on a separate bot before the real delivery on 1 January. The medium and maximum plans and frame-based moderation are later stages.

## 10. Expected scale

- From about 50 to 15000 participants.
- Resource sizing is defined in the infrastructure spec.