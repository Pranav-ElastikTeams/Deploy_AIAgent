# Ethics Case Screener

## Production Deployment

- Use Gunicorn or another WSGI server to run the Flask app in production:
  ```bash
  gunicorn -k eventlet -w 1 app:app
  ```
- Set all secrets and configuration in environment variables (see `.env.example`).
- Never use Flask's built-in server in production.
- Use HTTPS and set secure cookie flags.
- Restrict CORS and allowed origins for SocketIO.
- Monitor logs and errors using a logging/monitoring solution.

## Environment Variables

Copy `.env.example` to `.env` and fill in your production values.

## Security Best Practices

- Never commit real secrets to version control.
- Use strong, unique secrets for all keys and passwords.
- Regularly update dependencies and monitor for vulnerabilities.
- Validate and sanitize all user input.
- Use a production database and email provider. 