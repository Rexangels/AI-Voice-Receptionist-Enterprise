# GTM Playbook: The "After-Hours Mystery Caller" Loom Audit System

## 1. Waterfall Data Enrichment Stack (85%–92% Find Rate, <1.4% Bounce Rate)
1. **Source Raw Local Targets:** Extract Dental Practices or HVAC Contractors ($1M–$10M revenue, 30–80 calls/day, Google Maps Rank #4–#15) via Google Maps scraper + Apollo.io.
2. **Pipe into Clay Waterfall Enrichment:** Sequentially query 150+ data providers for verified owner/practice-manager emails and mobile numbers.
3. **Run Claygent Automated Pre-Call Research:** Scrape each target's website and Google reviews for:
   - Missing real-time booking widgets
   - Active Google Local Services Ads / Search Ads (high cost-per-click leakage when calls go unanswered)
   - 1-star or 2-star reviews mentioning *"no one answers the phone"* or *"impossible to schedule"*
4. **Sending Infrastructure:** Send exclusively from 3–5 warmed secondary domains on Smartlead.ai or Instantly (never your primary agency domain).

---

## 2. The After-Hours Mystery Call Protocol (5:30 PM – 7:30 PM)
Call 30 target clinics after 5:30 PM on a weekday or Saturday afternoon. Log the exact failure mode:
- `VOICEMAIL_GENERIC`: Rolls to standard voicemail box.
- `RING_NO_ANSWER`: Rings 8+ times with no pickup.
- `LEGACY_CALL_CENTER`: Slow operator takes a static paper/email message with zero calendar access.

---

## 3. The 90-Second Personalized Loom Video Script

- **0:00 – 0:20 (The Undeniable Observation):**
  *"Hey Dr. [Last Name], I called [Clinic Name]'s main line yesterday at 6:15 PM asking about a new-patient dental implant consultation, and it went straight to standard voicemail. Across [City], practices miss 20% to 30% of inbound inquiries this way—and at $450+ per visit, missing just two calls a week leaks over $3,600 every month to the clinic down the road."*
- **0:20 – 0:55 (Live Speakerphone Proof):**
  *(Hold up your phone and dial your pre-configured AI Receptionist demo line on speakerphone.)*
  *"I went ahead and configured an AI Receptionist specifically for [Clinic Name]. Listen to how fast it picks up, verifies Delta Dental PPO, and locks an appointment directly into the calendar without double-booking."*
- **0:55 – 1:30 (Risk-Free Call to Action):**
  *"I included the live test number right below this video so you can call and try interrupting it from your own cell phone. We can deploy this on your after-hours and overflow lines in 72 hours on a 14-day pilot. Reply 'PILOT' or grab 10 minutes on my calendar below."*

---

## 4. 4-Step Follow-Up Cadence (58.6% of Positive Replies Arrive in Steps 2–4)
- **Day 1 (Email + LinkedIn Connect):** Subject: `Called [Clinic Name] at 6:15 PM yesterday (2-min video)`
- **Day 3 (Follow-up #1):** Provide the live test phone number in bold so the owner can dial it directly from their mobile screen.
- **Day 6 (Follow-up #2 - The Value Math):** Share the 1-line calculation of their estimated missed-call leakage based on their Google review volume.
- **Day 10 (Follow-up #3 - Permission to Close File):** Offer to hand the pre-built `[Clinic Name]` voice agent over to another practice in their zip code if they are at full capacity.
