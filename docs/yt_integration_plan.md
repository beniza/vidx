# VIDX — YouTube Integration & Publishing Architecture Plan

This document outlines the technical design, industry best practices, and architectural roadmap for integrating automated YouTube publishing into the **VIDX Scripture Video Generator**.

---

## 🚨 Industry Reality Check: The YouTube API v3 Quota Challenge

Before designing any automated publishing feature, we must plan around a critical Google API constraint: **YouTube Data API v3 Daily Quotas**.

* Every Google Cloud Platform (GCP) project using the YouTube Data API receives a default allowance of **10,000 quota units per day**.
* **The Quota Cost of Publishing:**
  * Calling `videos.insert` (uploading a video file) costs **1,600 units**.
  * Calling `thumbnails.set` (attaching the generated `title_card.jpg` thumbnail) costs **50 units**.
  * Calling `playlistItems.insert` (adding the uploaded chapter to a Scripture playlist) costs **50 units**.
* **The Math:** A single complete chapter video upload consumes **~1,700 quota units**.
* **The Implication:** With standard default quotas, an automated tool can only publish **5 to 6 chapter videos per day** per API project before exhausting the daily limit! To upload an entire 16-chapter Gospel or a 260-chapter New Testament, our architecture MUST be designed for quota resilience, staged multi-day batching, and audit compliance (applying for a Google API quota extension).

---

## 🏛️ Architectural Options for VIDX

### Option 1: Native Synchronous Pipeline (`google-api-python-client`)
Embed OAuth 2.0 authentication directly into the VIDX rendering loop. As soon as a worker finishes rendering an MP4 and subtitle file, it immediately initiates a chunked, resumable upload to YouTube.
* **How it works:** Uses the **OAuth 2.0 Installed Application Flow** (opens a local browser tab for one-time login and caches a refresh token in `~/.vidx/youtube_token.json`). For headless remote terminals, it supports the **Device Authorization Grant** (displays a code to enter on a phone/laptop).
* **Pros:** Single-step command (`vidx -c project.yaml --publish`). Real-time upload progress can be merged into our existing interactive terminal monitor.
* **Cons:** Highly vulnerable to network interruptions and daily API quota exhaustion during long multi-chapter batch runs. If an upload fails on Chapter 7, it stalls the rendering pipeline.

### Option 2: Decoupled "Outbox / Manifest" Pattern ⭐ *(Recommended Automated Approach)*
Strictly separate video **generation** from video **distribution**.
* **How it works:**
  1. During rendering (`vidx -c project.yaml`), VIDX automatically generates a structured **Publishing Manifest (`publish_manifest.json` or `.csv`)** inside the output directory alongside the MP4s and thumbnails.
  2. The manifest pre-populates all YouTube metadata: video title, description (with verse ranges and copyright), privacy status (`private` by default for review), target playlist, tags, and thumbnail path.
  3. We introduce a dedicated publishing command: `vidx publish --manifest output/publish_manifest.json` (or `vidx -c project.yaml --publish`).
  4. **Smart Quota Manager:** The publisher tracks daily quota expenditure. If the 10,000-unit limit is approached after 5 videos, it cleanly pauses, marks completed items in the manifest as `"status": "UPLOADED"`, and advises the user when the daily quota resets—resuming seamlessly the next day without re-rendering!
* **Pros:**
  * **100% Resilient:** Network drops or API rate limits never waste CPU/GPU rendering time.
  * **Human-in-the-Loop Review:** Field coordinators can review or edit titles, spelling, and descriptions in the JSON/CSV manifest *before* launching the upload.
  * **Batch Staging:** Easily handles multi-day staged uploads for large New Testament projects.

### Option 3: Cloud Bucket / Zapier / Make.com Drop Folder Integration
* **How it works:** VIDX syncs finished MP4s and metadata JSON files to an enterprise cloud bucket (AWS S3, Google Drive, or Dropbox). An automated cloud workflow (Make.com, Zapier, or a custom AWS Lambda / Google Cloud Function) detects new files and handles the YouTube API publishing server-side.
* **Pros:** Eliminates local OAuth token management and local internet upload bandwidth issues for field technicians.
* **Cons:** Requires paid third-party subscriptions or cloud infrastructure maintenance by the organization.

### Option 4: "YouTube Studio Ready" Offline Package *(Essential Fallback)*
* **How it works:** For remote field translation teams operating with unstable internet or without Google API developer credentials, VIDX generates a clean `YouTube_Upload_Package/` folder for each chapter containing:
  * The `.mp4` video file.
  * The `.jpg` title card thumbnail.
  * A `metadata.txt` file formatted with exact titles, descriptions, chapters, and hashtags, optimized for one-click copy-pasting into YouTube Studio's web uploader.
* **Pros:** Zero API setup required; 100% immune to API quotas and authentication bugs.
* **Cons:** Manual web uploading required.

---

## 💡 Recommended Strategy: The Hybrid "Outbox" Strategy (Option 2 + Option 4)

We recommend implementing **Option 2 (Decoupled Outbox Manifest with Resumable Chunked Uploading)** as our primary automation engine, while automatically generating **Option 4 (Studio Ready Packages)** as a built-in fallback.

### 1. Proposed YAML Configuration Anatomy
We will extend `project.yaml` with a clean, optional `publishing` block:

```yaml
publishing:
  platform: "youtube"
  enabled: false                    # Set true or pass CLI flag --publish
  client_secrets_file: "~/.vidx/client_secrets.json" # Downloaded from Google Cloud Console
  privacy_status: "unlisted"        # 'private' (default for review), 'unlisted', or 'public'
  category_id: "22"                 # '22' = People & Blogs, '27' = Education
  playlist_name: "Gospel of Mark — Sindhi Translation"
  
  # Metadata Templates (supports {book}, {chapter}, {language} placeholders)
  title_template: "{book} Chapter {chapter:02d} — {language} Audio Bible"
  description_template: |
    Listen to {book} Chapter {chapter} in {language}.
    
    Text Copyright: {text_copyright}
    Audio Copyright: {audio_copyright}
    Generated automatically by VIDX Scripture Video Engine.
  tags:
    - "AudioBible"
    - "Scripture"
    - "{language}"
    - "{book}"
```

### 2. Why this is Best Practice for VIDX:
1. **Resumable Chunked Uploads (`google-api-python-client`):** We will implement Google's official resumable media upload protocol. If a multi-gigabyte 4K upload drops at 88%, VIDX will resume from byte 88% rather than restarting from zero.
2. **Safety First (Review Status):** Defaulting uploads to `unlisted` or `private` allows ministry supervisors to review subtitle rendering and audio synchronization on YouTube before making videos public to the world.
3. **Zero Quota Traps:** The Decoupled Outbox ensures that if a user hits the 5-video daily quota limit, their 16 rendered chapter videos remain perfectly preserved, and upload can resume with a single command tomorrow.

---

## 🛠️ Implementation Roadmap

### Phase 1: Data & Manifest Layer
* Extend `vidx/config.py` to validate the `publishing:` YAML schema.
* Update `BatchRunner` to generate a structured `publish_manifest.json` after batch rendering completes.
* Create a templating utility to resolve `{book}`, `{chapter}`, and `{language}` variables into formatted titles and descriptions.

### Phase 2: Auth & API Engine (`vidx/youtube.py`)
* Integrate `google-auth-oauthlib`, `google-api-python-client`, and `google-auth-httplib2`.
* Implement the OAuth 2.0 Installed Application Flow (local browser loopback) and Device Authorization Grant (for headless terminals), saving credentials securely to `~/.vidx/youtube_token.json`.
* Build the resumable chunked upload engine with rate-limit and quota-tracking logic.

### Phase 3: CLI & Progress Integration
* Add the `vidx publish` command (`--manifest`, `--resume`, `--dry-run`).
* Connect upload transfer speeds, uploaded bytes, and quota counters to the interactive terminal monitor.
* Generate offline "YouTube Studio Ready" packages when API publishing is disabled or offline.
