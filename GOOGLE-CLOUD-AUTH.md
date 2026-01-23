# Google Cloud Authentication Setup

The OAuth redirect error means Google is trying to redirect to `localhost:8085` but nothing is listening there.

## Option 1: Use Service Account (Recommended for Local Dev)

This is easier and doesn't require OAuth redirects.

### Steps:

1. **Create a Service Account:**
   ```bash
   gcloud iam service-accounts create signalops-ai \
     --display-name="SignalOps AI Service Account"
   ```

2. **Grant necessary permissions:**
   ```bash
   gcloud projects add-iam-policy-binding resume-agent-484309 \
     --member="serviceAccount:signalops-ai@resume-agent-484309.iam.gserviceaccount.com" \
     --role="roles/aiplatform.user"
   ```

3. **Create and download key:**
   ```bash
   gcloud iam service-accounts keys create signalops-ai-key.json \
     --iam-account=signalops-ai@resume-agent-484309.iam.gserviceaccount.com
   ```

4. **Set environment variable:**
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/signalops-ai-key.json"
   ```

5. **Update backend code to use service account:**
   The code will automatically use this if `GOOGLE_APPLICATION_CREDENTIALS` is set.

## Option 2: Use Application Default Credentials (ADC)

1. **Authenticate:**
   ```bash
   gcloud auth application-default login --no-launch-browser
   ```

2. **Or set project:**
   ```bash
   gcloud config set project resume-agent-484309
   gcloud auth application-default login
   ```

## Option 3: Skip Authentication (Fallback Mode)

If you don't want to set up Google Cloud right now, the system will work in **fallback mode**:
- Basic incident summaries (no LLM)
- Simple log answers (no LLM)

The system is fully functional without AI - you can add it later!

## Quick Fix for Current Error

The OAuth redirect is failing. You can:

1. **Cancel the OAuth flow** - Close the browser window
2. **Use service account instead** (Option 1 above)
3. **Or continue without AI** - System works in fallback mode

## Testing Without Vertex AI

The system works perfectly without Vertex AI configured:
- ✅ All log features work
- ✅ All alert features work  
- ✅ Basic summaries (log counts, patterns)
- ✅ Simple answers (log content)

You can add Vertex AI later when ready!
