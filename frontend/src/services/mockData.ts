import type { Complaint } from "../types";

/**
 * Seed history for demo mode.
 *
 * Every record below is entirely synthetic: written from scratch for this
 * demo, not adapted or paraphrased from any real FIR, news report, or case
 * file. No proper names, addresses, employers, or other identifying details
 * appear anywhere in this file — narratives use only generic relational
 * descriptors ("my neighbour", "a senior colleague") and unspecific
 * locations ("near the market"). This is enforced deliberately, not
 * incidentally: do not add a real name, a specific place, or any detail
 * drawn from an actual incident to this file. The UI surfaces this same
 * disclosure to viewers (see HistoryPage). Structure matches the live API
 * response exactly.
 */
export const MOCK_COMPLAINTS: Complaint[] = [
  {
    complaint_id: 41,
    complaint_text:
      "The accused acted fatally during the incident, attacking the victim with a sharp weapon following a dispute outside a residence in the late hours. Neighbours reported hearing an argument shortly before the attack.",
    received_at: "2026-09-07T14:22:10",
    sections: [
      { code: "302", title: "Murder", confidence: 0.91 },
      { code: "324", title: "Hurt by Dangerous Weapon", confidence: 0.58 },
    ],
    priority: { level: "High", score: 7.4 },
    routing: { unit: "Crime Branch", reason: "Section 302 is cognizable and non-bailable." },
    explanation: [
      { token: "fatally", weight: 0.42 },
      { token: "weapon", weight: 0.31 },
      { token: "attacking", weight: 0.24 },
      { token: "dispute", weight: 0.11 },
    ],
  },
  {
    complaint_id: 40,
    complaint_text:
      "I received a message claiming to be from my bank asking me to verify a UPI transaction. After entering the OTP, my bank account was debited twice without my authorization. I believe this was a phishing attempt.",
    received_at: "2026-09-06T09:41:55",
    sections: [
      { code: "66D", title: "Cheating by Personation (IT Act)", confidence: 0.87 },
      { code: "420", title: "Cheating", confidence: 0.64 },
    ],
    priority: { level: "Medium", score: 5.8 },
    routing: { unit: "Cyber Cell", reason: "Section 66D of the IT Act covers cheating by personation using computer resources." },
    explanation: [
      { token: "phishing", weight: 0.39 },
      { token: "OTP", weight: 0.33 },
      { token: "debited", weight: 0.27 },
      { token: "unauthorized", weight: 0.18 },
    ],
  },
  {
    complaint_id: 39,
    complaint_text:
      "Two men on a motorcycle snatched my chain near the market and pushed me to the ground when I resisted, causing hurt to my arm. This happened in broad daylight around 6 PM.",
    received_at: "2026-09-05T18:12:40",
    sections: [
      { code: "379", title: "Theft", confidence: 0.79 },
      { code: "323", title: "Voluntarily Causing Hurt", confidence: 0.61 },
    ],
    priority: { level: "Medium", score: 6.1 },
    routing: { unit: "Local Police Station", reason: "Section 379 (Theft) is handled at the jurisdictional station level." },
    explanation: [
      { token: "snatched", weight: 0.36 },
      { token: "pushed", weight: 0.22 },
      { token: "resisted", weight: 0.16 },
    ],
  },
  {
    complaint_id: 38,
    complaint_text:
      "My neighbour plays loud music every night past midnight despite repeated requests to stop, causing significant disturbance and nuisance to the entire building.",
    received_at: "2026-09-04T21:03:12",
    sections: [{ code: "268", title: "Public Nuisance", confidence: 0.73 }],
    priority: { level: "Low", score: 2.1 },
    routing: { unit: "Local Police Station", reason: "Section 268 (Public Nuisance) is a low-severity civic matter handled locally." },
    explanation: [
      { token: "loud music", weight: 0.29 },
      { token: "disturbance", weight: 0.24 },
      { token: "nuisance", weight: 0.21 },
    ],
  },
  {
    complaint_id: 37,
    complaint_text:
      "My daughter has been continuously harassed for dowry by her husband and in-laws since her marriage. She was recently threatened with harm if her family does not pay an additional amount.",
    received_at: "2026-09-04T11:27:33",
    sections: [
      { code: "498A", title: "Cruelty by Husband or Relatives", confidence: 0.88 },
      { code: "506", title: "Criminal Intimidation", confidence: 0.55 },
    ],
    priority: { level: "High", score: 7.8 },
    routing: { unit: "Women's Cell", reason: "Section 498A cases are routed to the Women's Cell for sensitive handling." },
    explanation: [
      { token: "dowry", weight: 0.44 },
      { token: "harassed", weight: 0.34 },
      { token: "threatened", weight: 0.27 },
    ],
  },
  {
    complaint_id: 36,
    complaint_text:
      "My six-year-old son was kidnapped from outside our home while playing. A witness saw him being forcibly taken into a vehicle in the afternoon. We have not been contacted since.",
    received_at: "2026-09-03T16:55:02",
    sections: [{ code: "363", title: "Kidnapping", confidence: 0.94 }],
    priority: { level: "High", score: 8.6 },
    routing: { unit: "Crime Branch", reason: "Section 363 (Kidnapping) mandates urgent inter-jurisdictional coordination." },
    explanation: [
      { token: "kidnapped", weight: 0.48 },
      { token: "forcibly taken", weight: 0.37 },
      { token: "witness", weight: 0.14 },
    ],
  },
  {
    complaint_id: 35,
    complaint_text:
      "An unknown person has created a fake profile using my photographs and has been sending unwanted messages to my contacts. I have also noticed that I am being followed near my workplace.",
    received_at: "2026-09-02T13:19:47",
    sections: [
      { code: "66C", title: "Identity Theft (IT Act)", confidence: 0.81 },
      { code: "354D", title: "Stalking", confidence: 0.62 },
    ],
    priority: { level: "Medium", score: 6.5 },
    routing: { unit: "Cyber Cell", reason: "Offences under the IT Act are routed to the Cyber Cell." },
    explanation: [
      { token: "fake profile", weight: 0.4 },
      { token: "followed", weight: 0.29 },
      { token: "unwanted messages", weight: 0.23 },
    ],
  },
  {
    complaint_id: 34,
    complaint_text:
      "A local shop owner has repeatedly threatened me over a business dispute, warning me to withdraw my complaint or face consequences for my family.",
    received_at: "2026-09-01T10:08:19",
    sections: [{ code: "506", title: "Criminal Intimidation", confidence: 0.76 }],
    priority: { level: "Low", score: 3.4 },
    routing: { unit: "Local Police Station", reason: "Section 506 (Criminal Intimidation) is assessed at the jurisdictional station level." },
    explanation: [
      { token: "threatened", weight: 0.33 },
      { token: "warned to withdraw", weight: 0.26 },
    ],
  },
  {
    complaint_id: 33,
    complaint_text:
      "Three armed men stopped my car late at night, threatened me with a knife, and robbed me of cash and my mobile phone before fleeing on foot.",
    received_at: "2026-08-31T23:41:08",
    sections: [
      { code: "392", title: "Robbery", confidence: 0.89 },
      { code: "324", title: "Hurt by Dangerous Weapon", confidence: 0.52 },
    ],
    priority: { level: "High", score: 7.9 },
    routing: { unit: "Crime Branch", reason: "Section 392 (Robbery) is cognizable and requires immediate investigation." },
    explanation: [
      { token: "robbed", weight: 0.45 },
      { token: "knife", weight: 0.34 },
      { token: "armed", weight: 0.22 },
    ],
  },
  {
    complaint_id: 32,
    complaint_text:
      "I discovered that a cheque submitted for a property transaction carried forged signatures that did not match the original documents held by the registrar.",
    received_at: "2026-08-30T15:33:51",
    sections: [
      { code: "465", title: "Forgery", confidence: 0.83 },
      { code: "420", title: "Cheating", confidence: 0.49 },
    ],
    priority: { level: "Medium", score: 5.5 },
    routing: { unit: "Economic Offences Wing", reason: "Section 465 (Forgery) requires document verification by the Economic Offences Wing." },
    explanation: [
      { token: "forged", weight: 0.41 },
      { token: "signatures", weight: 0.22 },
      { token: "documents", weight: 0.13 },
    ],
  },
  {
    complaint_id: 31,
    complaint_text:
      "A senior colleague has made repeated unwelcome advances and inappropriate comments towards me at the workplace despite being asked to stop.",
    received_at: "2026-08-29T12:02:44",
    sections: [{ code: "354A", title: "Sexual Harassment", confidence: 0.85 }],
    priority: { level: "High", score: 7.1 },
    routing: { unit: "Women's Cell", reason: "Section 354A offences are directed to the Women's Cell." },
    explanation: [
      { token: "unwelcome advances", weight: 0.4 },
      { token: "inappropriate", weight: 0.3 },
    ],
  },
  {
    complaint_id: 30,
    complaint_text:
      "My motorcycle was stolen from outside my apartment complex overnight. The parking area has no functioning CCTV coverage.",
    received_at: "2026-08-28T08:15:29",
    sections: [{ code: "379", title: "Theft", confidence: 0.8 }],
    priority: { level: "Medium", score: 4.6 },
    routing: { unit: "Local Police Station", reason: "Section 379 (Theft) is handled at the jurisdictional station level." },
    explanation: [
      { token: "stolen", weight: 0.37 },
      { token: "overnight", weight: 0.14 },
    ],
  },
  {
    complaint_id: 29,
    complaint_text:
      "A mob of about twenty men, several armed with sticks and rods, gathered outside our shop over a land dispute and damaged property before dispersing.",
    received_at: "2026-08-27T17:48:03",
    sections: [
      { code: "147", title: "Rioting", confidence: 0.78 },
      { code: "324", title: "Hurt by Dangerous Weapon", confidence: 0.41 },
    ],
    priority: { level: "Medium", score: 6.8 },
    routing: { unit: "Crime Branch", reason: "Section 147 offences involving unlawful assembly are escalated to the Crime Branch." },
    explanation: [
      { token: "mob", weight: 0.38 },
      { token: "armed with sticks", weight: 0.29 },
      { token: "damaged", weight: 0.15 },
    ],
  },
  {
    complaint_id: 28,
    complaint_text:
      "I was contacted by someone claiming to represent a delivery company who obtained my card details through a fraudulent link and used them for unauthorized purchases.",
    received_at: "2026-08-26T14:27:18",
    sections: [
      { code: "66C", title: "Identity Theft (IT Act)", confidence: 0.75 },
      { code: "420", title: "Cheating", confidence: 0.58 },
    ],
    priority: { level: "Medium", score: 5.9 },
    routing: { unit: "Cyber Cell", reason: "Offences under the IT Act are routed to the Cyber Cell." },
    explanation: [
      { token: "fraudulent link", weight: 0.36 },
      { token: "unauthorized", weight: 0.25 },
      { token: "card details", weight: 0.19 },
    ],
  },
  {
    complaint_id: 27,
    complaint_text:
      "During a confrontation, the accused pulled out a knife and stabbed the victim before fleeing. The victim was rushed to hospital and remains in critical condition.",
    received_at: "2026-08-25T20:36:55",
    sections: [
      { code: "307", title: "Attempt to Murder", confidence: 0.9 },
      { code: "324", title: "Hurt by Dangerous Weapon", confidence: 0.66 },
    ],
    priority: { level: "High", score: 8.9 },
    routing: { unit: "Crime Branch", reason: "Section 307 involves grievous intent and is treated as a serious cognizable offence." },
    explanation: [
      { token: "stabbed", weight: 0.46 },
      { token: "knife", weight: 0.32 },
      { token: "critical condition", weight: 0.21 },
    ],
  },
  {
    complaint_id: 26,
    complaint_text:
      "During a routine check, a quantity of suspected narcotics was found concealed in a vehicle registered to the accused, who could not produce any valid documentation.",
    received_at: "2026-08-24T22:14:09",
    sections: [{ code: "NDPS-20", title: "Possession of Narcotic Substances", confidence: 0.86 }],
    priority: { level: "High", score: 7.6 },
    routing: { unit: "Anti-Narcotics Cell", reason: "Offences under the NDPS Act are routed to the Anti-Narcotics Cell." },
    explanation: [
      { token: "narcotics", weight: 0.43 },
      { token: "concealed", weight: 0.24 },
    ],
  },
  {
    complaint_id: 25,
    complaint_text:
      "A neighbouring landowner has encroached upon a portion of my property and entered the premises without permission to construct a boundary wall.",
    received_at: "2026-08-23T09:52:37",
    sections: [{ code: "447", title: "Criminal Trespass", confidence: 0.7 }],
    priority: { level: "Low", score: 1.8 },
    routing: { unit: "Local Police Station", reason: "Section 447 (Criminal Trespass) is a minor offence handled at the station level." },
    explanation: [
      { token: "encroached", weight: 0.3 },
      { token: "without permission", weight: 0.17 },
    ],
  },
  {
    complaint_id: 24,
    complaint_text:
      "My sister is regularly beaten and harassed by her husband after consuming alcohol, and was hurt badly during the most recent incident last week.",
    received_at: "2026-08-22T19:05:21",
    sections: [
      { code: "498A", title: "Cruelty by Husband or Relatives", confidence: 0.84 },
      { code: "323", title: "Voluntarily Causing Hurt", confidence: 0.6 },
    ],
    priority: { level: "High", score: 7.3 },
    routing: { unit: "Women's Cell", reason: "Section 498A cases are routed to the Women's Cell for sensitive handling." },
    explanation: [
      { token: "beaten", weight: 0.39 },
      { token: "harassed", weight: 0.28 },
      { token: "hurt", weight: 0.2 },
    ],
  },
];
