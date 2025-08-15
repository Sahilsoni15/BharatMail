# MailApp Deployment Guide

This guide will help you deploy your Flask-based MailApp to Railway or Render.

## Pre-requisites

1. **Git Repository**: Your code should be in a Git repository (GitHub, GitLab, etc.)
2. **Firebase Setup**: Your Firebase project should be set up and the service account JSON file should be available
3. **Templates and Static Files**: Make sure you have all HTML templates and static files in your project

## Option 1: Deploy to Railway

Railway is excellent for Python applications and offers a generous free tier.

### Steps:

1. **Create Railway Account**
   - Go to [railway.app](https://railway.app)
   - Sign up with your GitHub account

2. **Prepare Your Code**
   - Make sure all the files we created are in your repository:
     - `Procfile`
     - `railway.json`
     - `runtime.txt`
     - `requirements.txt` (updated with gunicorn)
     - `.env.example`

3. **Upload Firebase Credentials**
   - In your project, create a folder called `credentials`
   - Upload your `bharatmail-3698e-firebase-adminsdk-fbsvc-2fd927c19d.json` file there
   - Update `firebase.py` to use the correct path:
   ```python
   cred = credentials.Certificate("credentials/bharatmail-3698e-firebase-adminsdk-fbsvc-2fd927c19d.json")
   ```

4. **Deploy to Railway**
   - Click "New Project" in Railway dashboard
   - Choose "Deploy from GitHub repo"
   - Select your repository
   - Railway will automatically detect it's a Python app and deploy

5. **Set Environment Variables**
   - In Railway dashboard, go to your project
   - Click on "Variables" tab
   - Add these environment variables:
     - `SECRET_KEY`: Generate a secure random key
     - `FLASK_ENV`: `production`
     - `PORT`: Railway will set this automatically

6. **Access Your App**
   - Railway will provide a URL like `https://your-app-name.up.railway.app`

---

## Option 2: Deploy to Render

Render is another excellent platform with good Python support.

### Steps:

1. **Create Render Account**
   - Go to [render.com](https://render.com)
   - Sign up with your GitHub account

2. **Prepare Your Code**
   - Ensure you have the `render.yaml` file in your repository
   - All other files should already be prepared

3. **Upload Firebase Credentials**
   - Same as Railway - create a `credentials` folder
   - Upload your Firebase service account JSON file
   - Update the path in `firebase.py`

4. **Deploy to Render**
   - In Render dashboard, click "New +"
   - Choose "Web Service"
   - Connect your GitHub repository
   - Render will use the settings from `render.yaml`

5. **Configure Environment Variables**
   - In the service settings, add:
     - `SECRET_KEY`: Generate a secure random key
     - Any other variables from `.env.example`

6. **Deploy**
   - Click "Create Web Service"
   - Render will build and deploy your app
   - You'll get a URL like `https://your-app-name.onrender.com`

---

## Important Security Notes

### 1. Firebase Service Account
- **Never commit your Firebase JSON file to Git**
- Upload it directly to your hosting platform
- Consider using environment variables for sensitive Firebase configs

### 2. Secret Key
- Generate a strong secret key for Flask sessions
- Use a tool like `python -c 'import secrets; print(secrets.token_hex())'`
- Never use the default development key in production

### 3. Environment Variables
- Set `FLASK_ENV=production` to disable debug mode
- Set proper `SECRET_KEY`
- Verify all sensitive data is in environment variables, not hardcoded

---

## Post-Deployment Checklist

1. **Test Registration**: Try creating a new user account
2. **Test Login**: Verify authentication works
3. **Test Email Sending**: Send a test email between users
4. **Test File Uploads**: Try uploading profile pictures
5. **Check Logs**: Monitor application logs for any errors

---

## Troubleshooting

### Common Issues:

1. **Firebase Connection Error**
   - Verify the service account JSON file path
   - Check Firebase database URL in your config

2. **Template Not Found**
   - Ensure all HTML templates are in the `templates/` folder
   - Check that the folder is included in your Git repository

3. **Static Files Not Loading**
   - Verify `static/` folder is in your repository
   - Check file paths in your templates

4. **Import Errors**
   - Make sure all dependencies are listed in `requirements.txt`
   - Check Python version compatibility

### Getting Help:

- **Railway**: Check their [docs](https://docs.railway.app) or Discord community
- **Render**: Check their [docs](https://render.com/docs) or support

---

## Next Steps

After successful deployment:

1. **Custom Domain**: Both platforms allow you to add custom domains
2. **SSL Certificate**: Automatically provided by both platforms
3. **Monitoring**: Set up error monitoring and logging
4. **Backups**: Consider backing up your Firebase data regularly

---

## Cost Considerations

- **Railway**: Generous free tier, pay-as-you-grow pricing
- **Render**: Free tier available, predictable pricing tiers

Both platforms are excellent choices for hosting Flask applications!
