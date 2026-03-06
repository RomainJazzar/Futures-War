/**
 * Futures War — Frontend Logic
 * Propriétaire : Rooney
 *
 * Gère : saisie texte, enregistrement audio, appel /api/pipeline,
 * affichage image, loader avec étapes, gestion erreurs.
 */

// ── DOM elements ────────────────────────────────
const btnGenerate = document.getElementById("btn-generate");
const btnMic = document.getElementById("btn-mic");
const btnMicStop = document.getElementById("btn-mic-stop");
const micStatus = document.getElementById("mic-status");
const micTimer = document.getElementById("mic-timer");
const textInput = document.getElementById("text-input");
const categorySelect = document.getElementById("category");
const loader = document.getElementById("loader");
const loaderText = document.getElementById("loader-text");
const errorDiv = document.getElementById("error");
const resultDiv = document.getElementById("result");
const resultImage = document.getElementById("result-image");
const resultOriginal = document.getElementById("result-original");
const resultEnriched = document.getElementById("result-enriched");
const resultSource = document.getElementById("result-source");
const resultCategory = document.getElementById("result-category");
const resultTime = document.getElementById("result-time");

// ── State ───────────────────────────────────────
let mediaRecorder = null;
let audioChunks = [];
let audioBlob = null;
let timerInterval = null;
let recordingSeconds = 0;
const MAX_RECORDING_SECONDS = 30;

// ── Audio recording ─────────────────────────────

btnMic.addEventListener("click", async () => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        // Already recording — stop
        stopRecording();
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioChunks = [];
        audioBlob = null;
        recordingSeconds = 0;

        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) audioChunks.push(e.data);
        };
        mediaRecorder.onstop = () => {
            audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
            stream.getTracks().forEach((t) => t.stop());
            clearInterval(timerInterval);

            // Update UI
            btnMic.classList.remove("recording");
            btnMic.textContent = "🎤 Parler";
            micStatus.classList.add("hidden");
            textInput.placeholder = `Audio enregistré (${recordingSeconds}s). Cliquez "Imaginer le futur" pour générer.`;
        };

        mediaRecorder.start();
        btnMic.classList.add("recording");
        btnMic.textContent = "⏹ Arrêter";
        micStatus.classList.remove("hidden");

        // Timer
        timerInterval = setInterval(() => {
            recordingSeconds++;
            micTimer.textContent = `${recordingSeconds}s`;
            if (recordingSeconds >= MAX_RECORDING_SECONDS) {
                stopRecording();
            }
        }, 1000);
    } catch (err) {
        showError("Impossible d'accéder au micro. Vérifiez les permissions du navigateur.");
        console.error("Microphone error:", err);
    }
});

btnMicStop.addEventListener("click", stopRecording);

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
    }
}

// ── Pipeline call ───────────────────────────────

btnGenerate.addEventListener("click", () => runPipeline());

// Also allow Enter in textarea (Shift+Enter for newline)
textInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        runPipeline();
    }
});

async function runPipeline() {
    const text = textInput.value.trim();
    const category = categorySelect.value;
    const hasAudio = audioBlob !== null;
    const hasText = text.length > 0;

    if (!hasAudio && !hasText) {
        showError("Enregistrez un audio ou saisissez un texte pour commencer.");
        return;
    }

    // Reset UI
    hideError();
    resultDiv.classList.add("hidden");
    showLoader("Préparation…");
    btnGenerate.disabled = true;

    // Build FormData
    const formData = new FormData();
    formData.append("category", category);

    if (hasAudio) {
        // Determine file extension from MIME
        const mimeType = audioBlob.type || "audio/webm";
        const ext = mimeType.includes("mp4") ? "m4a" : mimeType.includes("webm") ? "webm" : "wav";
        formData.append("audio", audioBlob, `recording.${ext}`);
        updateLoader("Transcription de l'audio…");
    }

    if (hasText) {
        formData.append("text", text);
    }

    if (!hasAudio) {
        updateLoader("Enrichissement du prompt…");
    }

    try {
        const response = await fetch("/api/pipeline", {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: "Erreur inconnue" }));
            throw new Error(err.detail || `Erreur ${response.status}`);
        }

        updateLoader("Génération de l'image…");
        const data = await response.json();
        showResult(data);
    } catch (err) {
        showError(err.message || "Une erreur est survenue. Réessayez.");
        console.error("Pipeline error:", err);
    } finally {
        hideLoader();
        btnGenerate.disabled = false;
        // Reset audio state for next generation
        audioBlob = null;
        textInput.placeholder =
            "Ex : Je voudrais des jardins suspendus au-dessus du Vieux-Port avec des drones qui livrent des courses...";
    }
}

// ── UI helpers ──────────────────────────────────

const CATEGORY_NAMES = {
    se_loger: "Se loger",
    se_deplacer: "Se déplacer",
    manger: "Manger",
    se_divertir: "Se divertir",
    acces_nature: "Accès Nature",
    travailler: "Travailler",
};

function showResult(data) {
    resultImage.src = `data:image/png;base64,${data.image_base64}`;
    resultOriginal.textContent = data.prompt_original;
    resultEnriched.textContent = data.prompt_enriched;
    resultSource.textContent = data.source === "speech" ? "🎤 Voix" : "⌨️ Texte";
    resultCategory.textContent = CATEGORY_NAMES[data.category] || data.category;
    resultTime.textContent = `${data.generation_time_seconds}s`;
    resultDiv.classList.remove("hidden");
}

function showLoader(text) {
    loaderText.textContent = text;
    loader.classList.remove("hidden");
}

function updateLoader(text) {
    loaderText.textContent = text;
}

function hideLoader() {
    loader.classList.add("hidden");
}

function showError(message) {
    errorDiv.textContent = message;
    errorDiv.classList.remove("hidden");
}

function hideError() {
    errorDiv.classList.add("hidden");
}
