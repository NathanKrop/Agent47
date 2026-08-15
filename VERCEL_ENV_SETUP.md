# Vercel Environment Variables Setup Guide

## Required Environment Variables for Vercel Deployment

Add these environment variables in **Vercel Dashboard** → **Settings** → **Environment Variables** (Production):

### 1. Database Connection (CRITICAL)
```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.iotvgfonbizqgjvrhgyf.supabase.co:5432/postgres
```

### 2. Dashboard Authentication
```
DASHBOARD_API_KEY=your-secret-api-key-here
```
- Leave empty to allow public access (no authentication)
- Set to any string to require `X-API-Key` header for dashboard access

### 3. SendGrid Email Service
```
SENDGRID_API_KEY=sg_your_key_here
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
```

### 4. WhatsApp Integration (Africa's Talking)
```
WHATSAPP_API_TOKEN=your_whatsapp_token
WHATSAPP_API_URL=https://graph.facebook.com/v20.0
WHATSAPP_SENDER_ID=your_sender_id
```

### 5. SMS Integration (Africa's Talking)
```
AT_API_KEY=your_africastalking_key
AT_USERNAME=your_at_username
```

### 6. Google Maps Integration (Optional)
```
GOOGLE_MAPS_API_KEY=your_google_maps_key
GOOGLE_PLACES_API_KEY=your_google_places_key
```

### 7. Application Settings
```
DRY_RUN=false
CELERY_TASK_ALWAYS_EAGER=true
HEADLESS=true
```

## How to Add Environment Variables in Vercel

1. Go to: https://vercel.com/dashboard/agent47-eta.vercel.app/settings/environment-variables
2. Click **"Add New Environment Variable"**
3. Enter:
   - **Name:** (e.g., `DASHBOARD_API_KEY`)
   - **Value:** (e.g., `test-key-12345`)
   - **Environment:** Select "Production" (or All)
4. Click **"Save"**
5. Vercel automatically redeploys with the new variables

## Testing the Deployment

Once environment variables are set:

1. **Health Check:**
   ```
   curl https://agent47-eta.vercel.app/api/health
   ```
   Expected response: `{"status":"ok"}`

2. **Dashboard with Auth:**
   ```
   curl -H "X-API-Key: your-secret-api-key" https://agent47-eta.vercel.app/
   ```

3. **Dashboard without Auth (if DASHBOARD_API_KEY is empty):**
   ```
   curl https://agent47-eta.vercel.app/
   ```

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| 401 Unauthorized | Set `DASHBOARD_API_KEY` environment variable |
| 500 Internal Server Error | Check DATABASE_URL is valid and Supabase is reachable |
| 404 Not Found | Ensure deployment is Ready status in Vercel |
| Database connection timeout | Verify Supabase connection string and network access |

## Security Reminders

⚠️ **AFTER** deployment:
1. Rotate your Supabase database password in Supabase Settings
2. Never commit `.env` files to Git
3. Keep API keys secure in environment variables only
4. Use strong DASHBOARD_API_KEY if protecting the dashboard
