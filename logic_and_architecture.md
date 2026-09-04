# Complete Logic & Architecture: RosoTravel AI Model Comparison POC

## 1. Project Overview
The RosoTravel AI Model Comparison POC is a full-stack web application designed to benchmark, verify, and compare AI-generated travel content across multiple Large Language Models (LLMs) via OpenRouter. The core objective is to ensure that generated content adheres strictly to specific guidelines (Length, Banned Keywords, Tone, Audience, Style, and Target Language) and to automatically regenerate and fix content that fails these checks.

---

## 2. System Architecture (High-Level)

The system follows a classic decoupled client-server architecture with dual-layer persistence.

*   **Frontend (Client):** React 18, TypeScript, Vite. Handles UI, state management, and user interactions.
*   **Backend (API):** Python, FastAPI. Handles business logic, LLM compilation, and verification.
*   **LLM Gateway:** OpenRouter API (Access to OpenAI, Anthropic, Google, Meta, DeepSeek, etc.)
*   **Database:** Supabase (PostgreSQL) with a seamless In-Memory Fallback mechanism if the database is unreachable.

### Data Flow Execution
1.  **Input & Configuration:** User inputs JSON data and configures prompt parameters (Tone, Audience, Language, etc.) on the Frontend.
2.  **Prompt Compilation:** Backend receives the config and data, building a comprehensive System and User prompt.
3.  **Generation Call:** Backend sends the prompt to the selected LLM via OpenRouter.
4.  **Verification Engine:** Backend evaluates the LLM output against 5 strict rules (Code-based and LLM-based).
5.  **Targeted Regeneration:** If verification fails, the Backend identifies failing parameters and asks the LLM to fix *only* those issues.
6.  **Persistence:** Every step, prompt, and output is logged in the database for auditing and side-by-side comparison.

---

## 3. Backend Logic & Core Algorithms

### 3.1. Generation Logic (`app/main.py` & `app/openrouter.py`)
*   **Prompt Building:** Combines the source JSON data with user-selected parameters (Tone, Audience, Banned Keywords, Style Guide).
*   **Language Mandate:** Injects strict system instructions to force the LLM to output all text values in the selected `Target Language`.
*   **JSON Enforcement:** Instructs the LLM to return strictly valid JSON matching a predefined schema (Title, Introduction, Attractions, Activities, Best Time, Tips, FAQs). Uses `response_format: { "type": "json_object" }` in OpenRouter.
*   **Fallback Mechanism:** If the OpenRouter API key is missing or credits run out (HTTP 402), the system injects *Model-Specific Mock Content* so the UI remains testable.

### 3.2. The Verification Engine (`app/verification.py`)
After generation, the content undergoes a 5-Parameter Quality Check:

1.  **Content Length (Code-based Check):**
    *   *Logic:* Extracts all text values from the JSON. Counts words. Compares against the user's `Target Word Count` ± a configurable `Tolerance %` (default 50%).
2.  **Banned Keywords (Code-based Check):**
    *   *Logic:* Uses Regex whole-word matching (`\bkeyword\b`) against all text values to ensure prohibited words were not used.
3.  **Tone (LLM-based Check):**
    *   *Logic:* If the user specified a Tone, a secondary LLM call (Verifier Model, e.g., GPT-4o) evaluates the text. If left blank, it auto-PASSes.
4.  **Audience Variant (LLM-based Check):**
    *   *Logic:* Similar to Tone, evaluated by the Verifier Model if specified.
5.  **Style Guide (LLM-based Check):**
    *   *Logic:* Verifier Model checks adherence to the custom style guide if provided.

### 3.3. Targeted Regeneration Logic
If *any* parameter fails verification:
1.  The system identifies exactly which parameters failed.
2.  It constructs a **Correction Prompt** containing the *previous JSON output* and a list of *Required Fixes* (e.g., "- Strictly adjust overall word count to be closer to 500 words").
3.  It calls the **SAME LLM** to fix its own mistakes.
4.  The new output is run through the Verification Engine again.

---

## 4. Database Schema & State (Supabase / In-Memory)

The system groups runs by `country + city + language` into a `Test Run`.
*   **`test_runs`**: The core context (Location, Language, Input JSON).
*   **`prompt_configs`**: The prompt rules (Tone, Audience, Length, Banned Keywords) tied to a Test Run.
*   **`generations`**: The actual LLM output, model name, status (Verified/Failed), cost, tokens, and latency. Tied to a Test Run.
*   **`verification_results`**: Logs every PASS/FAIL check for a generation.
*   **`regenerations`**: Snapshot of content before and after a targeted fix.
*   **`app_settings`**: Global config for the Verification Engine (tolerances, toggles, verifier model).

---

## 5. Proposed Frontend UI/UX Structure (Content Generation Page Focus)

To make the application intuitive, structured, and fail-safe, the UI for the **Content Generation Page** should follow a logical top-to-bottom layout with a mandatory confirmation step before hitting the costly LLM API.

### 5.1. Ideal Layout Structure (Where things should be placed)

**Left Column (The Input & Context Layer)**
1.  **Location & Language Block:** Fixed dropdowns for Country and City, and a selector for Target Language.
2.  **Source Data Block:** A clean interface to paste or upload the source JSON data. Should have a syntax highlighter or a clean textarea.

**Right Column (The Control & Execution Layer)**
3.  **Prompt Parameters Block:** Pill-based selectors for Tone, Audience. Input fields for Character Length and Banned Keywords. A textarea for the Custom Style Guide.
4.  **Model Selection:** Dropdown to pick the OpenRouter LLM.
5.  **Execution Button:** A prominent "Generate Content" button.

**Bottom Full-Width Section (The Output Layer - Appears Post-Generation)**
6.  **Results View:** Side-by-side or tabbed view showing the Generated Content (Formatted cleanly) and the Verification Logs (PASS/FAIL badges).

### 5.2. New Logic: The Final Prompt Confirmation Popup

**The Problem:** Currently, when the user clicks "Generate", it immediately hits the API. The user doesn't know exactly what prompt is being sent, which can lead to mistakes and wasted API costs.

**The Proposed Logic (Confirmation Flow):**
1.  User clicks **"Generate Content"**.
2.  Instead of calling the API, the Frontend triggers a **Full-Screen Modal / Popup (Alert Dialog)**.
3.  **Popup Content:**
    *   **Title:** Review Final Prompt
    *   **Body:** A read-only, syntax-highlighted code block displaying the *exact, compiled System and User prompts* (from the live compiler) that are about to be sent to the selected LLM.
    *   **Warning:** "You are about to execute a request using [Model Name]."
4.  **Popup Actions:**
    *   `Cancel / Edit Settings`: Closes the modal, allowing the user to tweak tone, keywords, etc.
    *   `Confirm & Execute`: Actually triggers the `POST /api/content/generate` API call and begins the loading state.

### Why this structure is better:
*   **Separation of Concerns:** Left side is "What are we talking about?", Right side is "How should the AI behave?".
*   **Transparency:** The Prompt Popup ensures the user understands how their UI selections translate into LLM instructions.
*   **Cost Efficiency:** Prevents accidental clicks and allows a final review of the data before consuming OpenRouter credits.
